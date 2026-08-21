import argparse
import ast
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

from deply.deply_runner import DeplyRunner


class TestModuleAwareDependencyResolution(unittest.TestCase):
    @staticmethod
    def _element_layer(name, file_regex, element_type):
        return {
            "name": name,
            "collectors": [
                {
                    "type": "file_regex",
                    "regex": file_regex,
                    "element_type": element_type,
                }
            ],
        }

    @classmethod
    def _function_layer(cls, name, file_regex):
        return cls._element_layer(name, file_regex, "function")

    @staticmethod
    def _function_name_layer(name, function_name_regex):
        return {
            "name": name,
            "collectors": [
                {
                    "type": "function_name_regex",
                    "function_name_regex": function_name_regex,
                }
            ],
        }

    def _run_deply(
            self,
            files,
            layers,
            ruleset,
            analysis_paths=None,
            return_errors=False,
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory) / "project"
            project_path.mkdir()

            for relative_path, source_code in files.items():
                file_path = project_path / relative_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(source_code)

            config_path = Path(temporary_directory) / "deply.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "deply": {
                            "paths": [
                                str(project_path / analysis_path)
                                for analysis_path in (analysis_paths or ["."])
                            ],
                            "layers": layers,
                            "ruleset": ruleset,
                        }
                    }
                )
            )
            runner = DeplyRunner(
                argparse.Namespace(
                    config=str(config_path),
                    parallel=None,
                    report_format="text",
                    output=None,
                    mermaid=False,
                    max_violations=0,
                )
            )

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                succeeded = runner.run()

            result = succeeded, list(runner.violations)
            if return_errors:
                return *result, list(runner.analysis_errors)
            return result

    def test_aliased_import_resolves_to_imported_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": "from package_a.service import target as run\n\ndef caller():\n    run()\n",
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_import_resolves_only_matching_module_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": "from package_a.service import target\n\ndef caller():\n    target()\n",
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target_b"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_relative_aliased_import_resolves_inside_package(self):
        succeeded, violations = self._run_deply(
            files={
                "app/__init__.py": "",
                "app/service.py": "def target():\n    pass\n",
                "app/caller.py": "from .service import target as run\n\ndef caller():\n    run()\n",
            },
            layers=[
                self._function_layer("target", r"app/service\.py$"),
                self._function_layer("caller", r"app/caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_module_alias_resolves_qualified_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": "import package_a.service as service\n\ndef caller():\n    service.target()\n",
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_module_attribute_dependency_is_attributed_to_assigned_variable(self):
        succeeded, violations = self._run_deply(
            files={
                "app/__init__.py": "",
                "app/models.py": "class Project:\n    pass\n",
                "app/queries.py": "from . import models\n\nqueryset = models.Project.objects.all()\n",
            },
            layers=[
                self._element_layer("models", r"app/models\.py$", "class"),
                self._element_layer("queries", r"app/queries\.py$", "variable"),
            ],
            ruleset={"queries": {"disallow_layer_dependencies": ["models"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"queryset"})
        self.assertEqual(
            {violation.dependency.depends_on_code_element.name for violation in violations},
            {"Project"},
        )

    def test_parameter_shadows_same_module_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller(target):\n    target()\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_assignment_shadows_same_module_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller():\n"
                    "    target = lambda: None\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_local_import_does_not_leak_to_sibling_function(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def first():\n"
                    "    from package_a.service import target\n"
                    "    target()\n\n"
                    "def second():\n"
                    "    pass\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("second", r"^second$"),
            ],
            ruleset={"second": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_local_aliased_import_resolves_inside_function(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    from package_a.service import target as run\n"
                    "    run()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_local_aliases_are_isolated_between_functions(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def first():\n"
                    "    from package_a.service import target as run\n"
                    "    run()\n\n"
                    "def second():\n"
                    "    from package_b.service import target as run\n"
                    "    run()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("first", r"^first$"),
                self._function_name_layer("second", r"^second$"),
            ],
            ruleset={
                "first": {"disallow_layer_dependencies": ["target_a"]},
                "second": {"disallow_layer_dependencies": ["target_b"]},
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                (
                    violation.element_name,
                    violation.dependency.depends_on_code_element.file.parent.name,
                )
                for violation in violations
            },
            {("first", "package_a"), ("second", "package_b")},
        )

    def test_assignment_replaces_local_import_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    from package_a.service import target as run\n"
                    "    run = lambda: None\n"
                    "    run()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.dependency_type for violation in violations},
            {"import_from"},
        )

    def test_assignment_replaces_local_module_import_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    import package_a.service as service\n"
                    "    service = object()\n"
                    "    service.target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.dependency_type for violation in violations},
            {"import"},
        )

    def test_relative_import_resolves_when_analysis_path_is_package_root(self):
        succeeded, violations = self._run_deply(
            files={
                "backend/app/__init__.py": "",
                "backend/app/service.py": "def target():\n    pass\n",
                "backend/app/caller.py": (
                    "from .service import target\n\n"
                    "def caller():\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
            analysis_paths=["backend/app"],
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_annotated_variable_initializer_dependency_is_attributed_to_variable(self):
        succeeded, violations = self._run_deply(
            files={
                "app/__init__.py": "",
                "app/models.py": "class Project:\n    pass\n",
                "app/queries.py": (
                    "from . import models\n\n"
                    "queryset: object = models.Project.objects.all()\n"
                ),
            },
            layers=[
                self._element_layer("models", r"app/models\.py$", "class"),
                self._element_layer("queries", r"app/queries\.py$", "variable"),
            ],
            ruleset={"queries": {"disallow_layer_dependencies": ["models"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"queryset"})
        self.assertEqual(
            {violation.dependency.depends_on_code_element.name for violation in violations},
            {"Project"},
        )

    def test_nested_function_identity_does_not_depend_on_collector_order(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    def caller():\n"
                    "        from package_a.service import target\n"
                    "        target()\n"
                    "    return caller()\n"
                ),
            },
            layers=[
                self._function_name_layer("caller", r"^caller$"),
                self._function_layer("target", r"package_a/service\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"outer.caller"})

    def test_import_prefers_matching_analysis_root(self):
        succeeded, violations = self._run_deply(
            files={
                "root_a/package_a/service.py": "def target():\n    pass\n",
                "root_b/package_a/service.py": "def target():\n    pass\n",
                "root_a/caller.py": (
                    "from package_a.service import target\n\n"
                    "def caller():\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_layer(
                    "target_a", r".*root_a/package_a/service\.py$"
                ),
                self._function_layer(
                    "target_b", r".*root_b/package_a/service\.py$"
                ),
                self._function_layer("caller", r".*root_a/caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
            analysis_paths=["root_a", "root_b"],
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.parent.name
                for violation in violations
            },
            {"root_a"},
        )

    def test_ambiguous_cross_root_import_fails_analysis(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "root_a/package_a/service.py": "def target():\n    pass\n",
                "root_b/package_a/service.py": "def target():\n    pass\n",
                "root_c/caller.py": (
                    "from package_a.service import target\n\n"
                    "def caller():\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_layer(
                    "target_a", r".*root_a/package_a/service\.py$"
                ),
                self._function_layer(
                    "target_b", r".*root_b/package_a/service\.py$"
                ),
                self._function_layer("caller", r".*root_c/caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
            analysis_paths=["root_a", "root_b", "root_c"],
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(violations, [])
        self.assertTrue(
            any("ambiguous internal import 'package_a.service.target'" in error
                for error in analysis_errors)
        )

    def test_comprehension_target_does_not_shadow_enclosing_function(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller():\n"
                    "    target()\n"
                    "    return [target for target in ()]\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {5},
        )

    def test_lambda_parameter_shadows_same_module_symbol(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller():\n"
                    "    return (lambda target: target())(lambda: None)\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_class_local_import_resolves_inside_class_body(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "class Caller:\n"
                    "    from package_a.service import target as run\n"
                    "    value = run()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._element_layer("caller", r"caller\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"Caller"})

    def test_function_default_resolves_before_parameter_scope(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller(target=target()):\n"
                    "    return target\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {4},
        )

    def test_invalid_relative_import_fails_analysis(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from .service import target\n\n"
                    "def caller():\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(violations, [])
        self.assertTrue(
            any("failed to resolve relative import '.service'" in error
                for error in analysis_errors)
        )

    def test_module_import_propagates_dependency_without_symbol_use(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "import package_a.service as service\n\n"
                    "def caller():\n"
                    "    pass\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.dependency_type for violation in violations},
            {"import"},
        )

    def test_bare_module_import_resolves_only_imported_module(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_a/other.py": "def target():\n    pass\n",
                "caller.py": (
                    "import package_a.service\n\n"
                    "def caller():\n"
                    "    package_a.service.target()\n"
                ),
            },
            layers=[
                self._function_layer("service", r"package_a/service\.py$"),
                self._function_layer("other", r"package_a/other\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["service", "other"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_package_import_does_not_depend_on_descendant_module(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/__init__.py": "",
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": "import package_a\n\ndef caller():\n    pass\n",
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_unknown_module_attribute_does_not_resolve_to_module_element(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "import package_a.service as service\n\n"
                    "def caller():\n"
                    "    service.unknown()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {1},
        )

    def test_nested_function_resolves_later_enclosing_import(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    def caller():\n"
                    "        target()\n"
                    "    from package_a.service import target\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"outer.caller"})
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {3},
        )

    def test_nested_function_ignores_shadowed_enclosing_import(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    from package_a.service import target as run\n"
                    "    run = lambda: None\n"
                    "    def caller():\n"
                    "        run()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_nested_function_ignores_import_shadowed_by_exhaustive_match(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    from package_a.service import target as run\n"
                    "    match object():\n"
                    "        case _:\n"
                    "            run = lambda: None\n"
                    "    def caller():\n"
                    "        run()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_nested_function_ignores_import_shadowed_by_definite_named_expr(self):
        shadowing_sources = ["    (run := lambda: None)\n"]
        if hasattr(ast, "Match"):
            shadowing_sources.append(
                "    match object():\n"
                "        case _:\n"
                "            (run := lambda: None)\n"
            )
        for shadowing_source in shadowing_sources:
            with self.subTest(shadowing_source=shadowing_source):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            "    from package_a.service import target as run\n"
                            f"{shadowing_source}"
                            "    def caller():\n"
                            "        run()\n"
                            "    return caller\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target",
                            r"package_a/service\.py$",
                        ),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {"disallow_layer_dependencies": ["target"]}
                    },
                )

                self.assertTrue(succeeded)
                self.assertEqual(violations, [])

    def test_nested_function_keeps_import_after_conditional_named_expr(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(condition):\n"
                    "    from package_a.service import target as run\n"
                    "    condition and (run := lambda: None)\n"
                    "    def caller():\n"
                    "        run()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"outer.caller"})

    def test_bool_op_named_expr_keeps_active_import_dependency(self):
        for operator in ("and", "or"):
            with self.subTest(operator=operator):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def caller(condition):\n"
                            "    from package_a.service import target as run\n"
                            f"    condition {operator} (run := lambda: None)\n"
                            "    run()\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target",
                            r"package_a/service\.py$",
                        ),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {"disallow_layer_dependencies": ["target"]}
                    },
                )

                self.assertFalse(succeeded)
                dependency_types = {
                    violation.dependency.dependency_type
                    for violation in violations
                }
                self.assertTrue(
                    {"function_call", "name_load"} <= dependency_types
                )

    def test_comprehension_assignment_expression_binds_enclosing_function(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "def caller():\n"
                    "    [target := item for item in ()]\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_pattern_captures_shadow_same_module_symbol(self):
        for pattern in ("target", "[*target]", "{**target}"):
            with self.subTest(pattern=pattern):
                succeeded, violations = self._run_deply(
                    files={
                        "module.py": (
                            "def target():\n    pass\n\n"
                            "def caller(value):\n"
                            "    match value:\n"
                            f"        case {pattern}:\n"
                            "            pass\n"
                            "    target()\n"
                        ),
                    },
                    layers=[
                        self._function_name_layer("target", r"^target$"),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {"disallow_layer_dependencies": ["target"]}
                    },
                )

                self.assertTrue(succeeded)
                self.assertEqual(violations, [])

    def test_class_definition_name_replaces_import_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target\n\n"
                    "class Caller:\n"
                    "    def target():\n"
                    "        pass\n"
                    "    value = target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._element_layer("caller", r"caller\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {1},
        )

    def test_conflicting_local_import_alias_emits_all_possible_dependencies(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    from package_a.service import target as run\n"
                    "    from package_b.service import target as run\n"
                    "    def caller():\n"
                    "        run()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
            },
            {"package_a", "package_b"},
        )

    def test_external_import_rebinding_keeps_possible_internal_dependency(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    from package_a.service import target as run\n"
                    "    import external_package as run\n"
                    "    def caller():\n"
                    "        run()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertEqual(
            {violation.dependency.depends_on_code_element.file.name for violation in violations},
            {"service.py"},
        )

    def test_sequential_local_import_rebinding_uses_statement_order(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    from package_a.service import target as run\n"
                    "    run()\n"
                    "    from package_b.service import target as run\n"
                    "    run()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertEqual(
            {
                (
                    violation.dependency.depends_on_code_element.file.parent.name,
                    violation.dependency.line,
                )
                for violation in violations
            },
            {
                ("package_a", 2),
                ("package_a", 3),
                ("package_b", 4),
                ("package_b", 5),
            },
        )

    def test_nested_comprehension_resolves_later_enclosing_import(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    def caller():\n"
                    "        return [target() for _ in ()]\n"
                    "    from package_a.service import target\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual({violation.element_name for violation in violations}, {"outer.caller"})

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_class_pattern_capture_replaces_import_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target\n\n"
                    "class Caller:\n"
                    "    match object():\n"
                    "        case target:\n"
                    "            pass\n"
                    "    value = target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._element_layer("caller", r"caller\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {1},
        )

    def test_class_for_iterable_resolves_before_target_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "class Caller:\n"
                    "    for target in (target,):\n"
                    "        pass\n"
                ),
            },
            layers=[
                self._function_layer("target", r"module\.py$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {5},
        )

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_refutable_class_pattern_does_not_hide_global_fallback(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "class Caller:\n"
                    "    match 2:\n"
                    "        case 1 as target:\n"
                    "            pass\n"
                    "    value = target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"module\.py$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {8},
        )

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_guarded_irrefutable_class_capture_hides_global_fallback(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "class Caller:\n"
                    "    match 2:\n"
                    "        case target if False:\n"
                    "            pass\n"
                    "    value = target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"module\.py$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_irrefutable_match_keeps_definite_body_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "class Caller:\n"
                    "    match object():\n"
                    "        case _:\n"
                    "            target = lambda: None\n"
                    "    value = target()\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_conditional_match_import_keeps_global_fallback(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "module.py": (
                    "def run():\n    pass\n\n"
                    "class Caller:\n"
                    "    match object():\n"
                    "        case 1:\n"
                    "            from package_a.service import target as run\n"
                    "        case _:\n"
                    "            pass\n"
                    "    value = run()\n"
                ),
            },
            layers=[
                self._function_layer(
                    "imported_target",
                    r"package_a/service\.py$",
                ),
                self._function_name_layer("global_target", r"^run$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["global_target"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {10},
        )

    def test_empty_class_for_keeps_global_fallback_in_else(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n    pass\n\n"
                    "class Caller:\n"
                    "    for target in ():\n"
                    "        pass\n"
                    "    else:\n"
                    "        value = target()\n"
                ),
            },
            layers=[
                self._function_layer("target", r"module\.py$"),
                self._element_layer("caller", r"module\.py$", "class"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {violation.dependency.line for violation in violations},
            {8},
        )


if __name__ == "__main__":
    unittest.main()
