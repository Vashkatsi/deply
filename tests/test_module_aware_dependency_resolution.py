import argparse
import ast
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

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
                    "from ..service import target\n\n"
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
            any("failed to resolve relative import '..service'" in error
                for error in analysis_errors)
        )

    def test_relative_import_value_error_fails_analysis(self):
        try:
            with patch(
                    "deply.code_analyzer.resolve_name",
                    side_effect=ValueError("no package specified"),
            ):
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
                    ruleset={
                        "caller": {"disallow_layer_dependencies": ["target"]}
                    },
                    return_errors=True,
                )
        except ValueError as exception:
            self.fail(f"ValueError escaped dependency analysis: {exception}")

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

    def test_nested_function_uses_last_local_import_binding(self):
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
            {"package_b"},
        )

    def test_external_import_rebinding_clears_internal_dependency(self):
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

        self.assertTrue(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertEqual(violations, [])

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

    def test_namespace_package_analysis_root_resolves_absolute_import(self):
        imports = {
            "absolute": "from namespace_package.service import target\n\n",
            "relative": "from .service import target\n\n",
        }
        for import_type, import_statement in imports.items():
            with self.subTest(import_type=import_type):
                succeeded, violations = self._run_deply(
                    files={
                        "namespace_package/service.py": "def target():\n    pass\n",
                        "namespace_package/caller.py": (
                            f"{import_statement}"
                            "def caller():\n"
                            "    target()\n"
                        ),
                    },
                    layers=[
                        self._function_layer("target", r"service\.py$"),
                        self._function_layer("caller", r"caller\.py$"),
                    ],
                    ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
                    analysis_paths=["namespace_package"],
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.name
                        for violation in violations
                    },
                    {"service.py"},
                )

    def test_conditional_class_bindings_keep_global_fallback(self):
        conditional_bindings = {
            "if": (
                "    if False:\n"
                "        target = lambda: None\n"
            ),
            "try": (
                "    try:\n"
                "        raise RuntimeError\n"
                "        target = lambda: None\n"
                "    except RuntimeError:\n"
                "        pass\n"
            ),
            "while": (
                "    while False:\n"
                "        target = lambda: None\n"
            ),
        }
        for statement_type, conditional_binding in conditional_bindings.items():
            with self.subTest(statement_type=statement_type):
                succeeded, violations = self._run_deply(
                    files={
                        "module.py": (
                            "def target():\n"
                            "    pass\n\n"
                            "class Caller:\n"
                            f"{conditional_binding}"
                            "    value = target()\n"
                        ),
                    },
                    layers=[
                        self._function_name_layer("target", r"^target$"),
                        self._element_layer("caller", r"module\.py$", "class"),
                    ],
                    ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.name
                        for violation in violations
                    },
                    {"target"},
                )

    def test_module_rebinding_uses_source_order(self):
        sources = {
            "definition_after_import": (
                "from package_a.service import target as run\n\n"
                "def run():\n"
                "    pass\n\n"
                "def caller():\n"
                "    run()\n"
            ),
            "import_after_definition": (
                "def run():\n"
                "    pass\n\n"
                "from package_a.service import target as run\n\n"
                "def caller():\n"
                "    run()\n"
            ),
        }
        for source_name, source in sources.items():
            with self.subTest(source_name=source_name):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": source,
                    },
                    layers=[
                        self._function_layer("imported", r"package_a/service\.py$"),
                        self._function_name_layer("local", r"^run$"),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={"caller": {"disallow_layer_dependencies": ["local"]}},
                )

                if source_name == "definition_after_import":
                    self.assertFalse(succeeded)
                    self.assertEqual(
                        {
                            violation.dependency.depends_on_code_element.name
                            for violation in violations
                        },
                        {"run"},
                    )
                else:
                    self.assertTrue(succeeded)
                    self.assertEqual(violations, [])

    def test_conditional_module_import_keeps_local_fallback(self):
        conditional_imports = {
            "if": (
                "if False:\n"
                "    from package_a.service import target as run\n"
            ),
            "try": (
                "try:\n"
                "    raise RuntimeError\n"
                "    from package_a.service import target as run\n"
                "except RuntimeError:\n"
                "    pass\n"
            ),
            "while": (
                "while False:\n"
                "    from package_a.service import target as run\n"
            ),
        }
        for statement_type, conditional_import in conditional_imports.items():
            with self.subTest(statement_type=statement_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def run():\n"
                            "    pass\n\n"
                            f"{conditional_import}\n"
                            "def caller():\n"
                            "    run()\n"
                        ),
                    },
                    layers=[
                        self._function_layer("imported", r"package_a/service\.py$"),
                        self._function_name_layer("local", r"^run$"),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={"caller": {"disallow_layer_dependencies": ["local"]}},
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.name
                        for violation in violations
                    },
                    {"run"},
                )

    def test_last_alias_in_single_import_wins(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    import package_a.service as service, package_b.service as service\n"
                    "    service.target()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_b"})

    def test_try_handler_uses_binding_before_guaranteed_error(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    try:\n"
                    "        import package_a.service as service\n"
                    "        1 / 0\n"
                    "        import package_b.service as service\n"
                    "    except Exception:\n"
                    "        service.target()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_a"})

    def test_module_try_handler_uses_binding_before_guaranteed_error(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "try:\n"
                    "    import package_a.service as service\n"
                    "    1 / 0\n"
                    "    import package_b.service as service\n"
                    "except Exception:\n"
                    "    value = service.target()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._element_layer("caller", r"caller\.py$", "variable"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_a"})

    def test_sequential_module_alias_rebinding_removes_old_descendants(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def old():\n    pass\n",
                "package_b/service.py": "def new():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    import package_a.service as service\n"
                    "    import package_b.service as service\n"
                    "    service.old()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            [
                violation
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            ],
            [],
        )

    def test_closure_uses_later_enclosing_import_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    def caller():\n"
                    "        service.target()\n"
                    "    import package_b.service as service\n"
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
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_b"})

    def test_module_calls_use_runtime_binding_order(self):
        sources = {
            "conditional_import": (
                "def run():\n"
                "    pass\n"
                "if __name__ == '__main__':\n"
                "    from package_a.service import target as run\n"
                "value = run()\n"
            ),
            "future_import": (
                "def run():\n"
                "    pass\n"
                "value = run()\n"
                "from package_a.service import target as run\n"
            ),
        }
        expected_targets = {
            "conditional_import": {("project", "run"), ("package_a", "target")},
            "future_import": {("project", "run")},
        }
        for source_name, source in sources.items():
            with self.subTest(source_name=source_name):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": source,
                    },
                    layers=[
                        self._function_layer("imported", r"package_a/service\.py$"),
                        self._function_name_layer("local", r"^run$"),
                        self._element_layer("caller", r"caller\.py$", "variable"),
                    ],
                    ruleset={
                        "caller": {
                            "disallow_layer_dependencies": ["imported", "local"]
                        }
                    },
                )

                self.assertFalse(succeeded)
                call_targets = {
                    (
                        violation.dependency.depends_on_code_element.file.parent.name,
                        violation.dependency.depends_on_code_element.name,
                    )
                    for violation in violations
                    if violation.dependency.dependency_type == "function_call"
                }
                self.assertEqual(call_targets, expected_targets[source_name])

    def test_handler_nested_function_keeps_qualified_identity(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    try:\n"
                    "        import package_a.service as service\n"
                    "        1 / 0\n"
                    "        import package_b.service as service\n"
                    "    except Exception:\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "        return caller\n"
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
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_a"})

    def test_handler_return_ignores_unreachable_later_rebinding(self):
        later_bindings = {
            "import": "    import package_b.service as service\n",
            "assignment": "    service = object()\n",
        }
        for binding_type, later_binding in later_bindings.items():
            with self.subTest(binding_type=binding_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            "    try:\n"
                            "        import package_a.service as service\n"
                            "        1 / 0\n"
                            "    except Exception:\n"
                            "        def caller():\n"
                            "            service.target()\n"
                            "        return caller\n"
                            f"{later_binding}"
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
                )

                self.assertFalse(succeeded)
                call_targets = {
                    violation.dependency.depends_on_code_element.file.parent.name
                    for violation in violations
                    if violation.dependency.dependency_type == "function_call"
                }
                self.assertEqual(call_targets, {"package_a"})

    def test_class_collector_qualifies_async_function_ancestor(self):
        succeeded, violations = self._run_deply(
            files={
                "module.py": (
                    "def target():\n"
                    "    pass\n\n"
                    "async def outer():\n"
                    "    if True:\n"
                    "        class Caller:\n"
                    "            value = target()\n"
                ),
            },
            layers=[
                self._function_name_layer("target", r"^target$"),
                {
                    "name": "caller",
                    "collectors": [
                        {
                            "type": "class_name_regex",
                            "class_name_regex": r"^Caller$",
                        }
                    ],
                },
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.name
                for violation in violations
            },
            {"target"},
        )

    def test_handler_return_applies_finally_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    try:\n"
                    "        import package_a.service as service\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "        return caller\n"
                    "    finally:\n"
                    "        import package_b.service as service\n"
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
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_b"})

    def test_closure_reaches_rebinding_after_local_control_flow_exit(self):
        outer_bodies = {
            "caught_raise": (
                "    try:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        raise RuntimeError\n"
                "    except RuntimeError:\n"
                "        import package_b.service as service\n"
            ),
            "caught_raise_then_rebinding": (
                "    try:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        raise RuntimeError\n"
                "    except RuntimeError:\n"
                "        pass\n"
                "    import package_b.service as service\n"
            ),
            "caught_nested_raise": (
                "    try:\n"
                "        if True:\n"
                "            import package_a.service as service\n"
                "            def caller():\n"
                "                service.target()\n"
                "            raise RuntimeError\n"
                "    except RuntimeError:\n"
                "        import package_b.service as service\n"
            ),
            "uncaught_raise": (
                "    import package_a.service as service\n"
                "    def caller():\n"
                "        service.target()\n"
                "    raise RuntimeError\n"
                "    import package_b.service as service\n"
            ),
            "raise_with_finally": (
                "    try:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        raise RuntimeError\n"
                "    finally:\n"
                "        import package_b.service as service\n"
            ),
            "uncaught_raise_with_empty_finally": (
                "    try:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        raise RuntimeError\n"
                "    finally:\n"
                "        pass\n"
                "    import package_b.service as service\n"
            ),
            "break": (
                "    for _ in [1]:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        break\n"
                "    import package_b.service as service\n"
            ),
            "continue": (
                "    for _ in [1]:\n"
                "        import package_a.service as service\n"
                "        def caller():\n"
                "            service.target()\n"
                "        continue\n"
                "    import package_b.service as service\n"
            ),
        }
        expected_targets = {
            "caught_raise": {"package_a", "package_b"},
            "caught_raise_then_rebinding": {"package_b"},
            "caught_nested_raise": {"package_a", "package_b"},
            "uncaught_raise": {"package_a"},
            "raise_with_finally": {"package_b"},
            "uncaught_raise_with_empty_finally": {"package_a"},
            "break": {"package_b"},
            "continue": {"package_b"},
        }
        for exit_type, outer_body in outer_bodies.items():
            with self.subTest(exit_type=exit_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            f"{outer_body}"
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
                )

                self.assertFalse(succeeded)
                call_targets = {
                    violation.dependency.depends_on_code_element.file.parent.name
                    for violation in violations
                    if violation.dependency.dependency_type == "function_call"
                }
                self.assertEqual(call_targets, expected_targets[exit_type])

    def test_closure_ignores_import_after_unconditional_return(self):
        succeeded, violations = self._run_deply(
            files={
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    def caller():\n"
                    "        service.target()\n"
                    "    return caller\n"
                    "    import package_b.service as service\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_b/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={"caller": {"disallow_layer_dependencies": ["target"]}},
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_lambda_uses_later_enclosing_import_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    caller = lambda: service.target()\n"
                    "    import package_b.service as service\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        call_targets = {
            violation.dependency.depends_on_code_element.file.parent.name
            for violation in violations
            if violation.dependency.dependency_type == "function_call"
        }
        self.assertEqual(call_targets, {"package_b"})

    def test_uncollected_module_binding_clears_import_call_target(self):
        shadowing_bindings = {
            "assignment": "run = lambda: None\n",
            "annotated_assignment": "run: object = lambda: None\n",
            "augmented_assignment": "run += 1\n",
            "deletion": "del run\n",
            "function": "def run():\n    pass\n",
            "class": "class run:\n    pass\n",
        }
        for binding_type, shadowing_binding in shadowing_bindings.items():
            with self.subTest(binding_type=binding_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "from package_a.service import target as run\n"
                            f"{shadowing_binding}"
                            "def caller():\n"
                            "    run()\n"
                        ),
                    },
                    layers=[
                        self._function_layer("target", r"package_a/service\.py$"),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {"disallow_layer_dependencies": ["target"]}
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    [
                        violation
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    ],
                    [],
                )

    def test_module_annotation_without_value_keeps_import_call_target(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target as run\n"
                    "run: object\n"
                    "def caller():\n"
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
            {
                violation.dependency.line
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {4},
        )

    def test_for_body_import_remains_possible_after_loop(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    for _ in [1]:\n"
                    "        from package_a.service import target\n"
                    "    target()\n"
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
            {
                violation.dependency.line
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {4},
        )

    def test_canonical_module_identity_wins_over_root_alias(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package/service.py": "def target():\n    pass\n",
                "project/package/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from project.package.service import target\n\n"
                    "def caller():\n"
                    "    target()\n"
                ),
            },
            layers=[
                self._function_layer("shallow", r"^package/service\.py$"),
                self._function_layer("nested", r"project/package/service\.py$"),
                self._function_layer("caller", r"caller\.py$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["shallow", "nested"]
                }
            },
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertEqual(
            {
                violation.message
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {
                "Layer 'caller' is not allowed to depend on layer 'nested'. "
                "Dependency type: function_call."
            },
        )

    def test_definite_finally_import_replaces_module_binding(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target as run\n"
                    "try:\n"
                    "    pass\n"
                    "finally:\n"
                    "    from package_b.service import target as run\n"
                    "def caller():\n"
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
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_indirect_module_rebinding_clears_import_call_target(self):
        rebindings = {
            "named_expression": "(run := lambda: None)\n",
            "with_target": (
                "from contextlib import nullcontext\n"
                "with nullcontext(lambda: None) as run:\n"
                "    pass\n"
            ),
            "finally_assignment": (
                "try:\n"
                "    pass\n"
                "finally:\n"
                "    run = lambda: None\n"
            ),
        }
        for binding_type, rebinding in rebindings.items():
            with self.subTest(binding_type=binding_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "from package_a.service import target as run\n"
                            f"{rebinding}"
                            "def caller():\n"
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
                        "caller": {
                            "disallow_layer_dependencies": ["target"]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    [
                        violation
                        for violation in violations
                        if violation.dependency.dependency_type
                        == "function_call"
                    ],
                    [],
                )

    def test_loop_else_sees_completed_body_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    for _ in [1]:\n"
                    "        import package_a.service as service\n"
                    "    else:\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_returning_if_branch_does_not_reach_following_closure(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(condition):\n"
                    "    import package_a.service as service\n"
                    "    if condition:\n"
                    "        import package_b.service as service\n"
                    "        return None\n"
                    "    def caller():\n"
                    "        service.target()\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_returning_try_handler_does_not_reach_following_closure(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    try:\n"
                    "        pass\n"
                    "    except Exception:\n"
                    "        import package_b.service as service\n"
                    "        return None\n"
                    "    def caller():\n"
                    "        service.target()\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_lambda_in_if_test_sees_body_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    if (caller := lambda: service.target()):\n"
                    "        import package_b.service as service\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_return_inside_finally_ignores_later_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    try:\n"
                    "        pass\n"
                    "    finally:\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "        return caller\n"
                    "        import package_b.service as service\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_generator_expression_uses_later_enclosing_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    result = (service.target() for _ in [1])\n"
                    "    import package_b.service as service\n"
                    "    return result\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_returning_match_case_does_not_reach_following_closure(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(value):\n"
                    "    import package_a.service as service\n"
                    "    match value:\n"
                    "        case 1:\n"
                    "            import package_b.service as service\n"
                    "            return None\n"
                    "        case _:\n"
                    "            pass\n"
                    "    def caller():\n"
                    "        service.target()\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_nested_raise_state_reaches_module_handler(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target as run\n"
                    "condition = bool()\n"
                    "try:\n"
                    "    if condition:\n"
                    "        from package_b.service import target as run\n"
                    "        raise RuntimeError\n"
                    "except RuntimeError:\n"
                    "    pass\n"
                    "def caller():\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a", "package_b"},
        )

    def test_finally_closure_sees_continuing_and_terminal_states(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(condition):\n"
                    "    import package_a.service as service\n"
                    "    try:\n"
                    "        if condition:\n"
                    "            import package_b.service as service\n"
                    "            return None\n"
                    "    finally:\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "        return caller\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a", "package_b"},
        )

    def test_lambda_in_while_test_sees_body_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    while (caller := lambda: service.target()):\n"
                    "        import package_b.service as service\n"
                    "        break\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_lambda_in_while_test_ignores_unreachable_body_rebinding(self):
        terminal_blocks = {
            "break": "        break\n",
            "with": "        with manager:\n            break\n",
            "if": (
                "        if bool():\n"
                "            break\n"
                "        else:\n"
                "            break\n"
            ),
            "try": (
                "        try:\n"
                "            break\n"
                "        finally:\n"
                "            pass\n"
            ),
        }
        for terminal_type, terminal_block in terminal_blocks.items():
            with self.subTest(terminal_type=terminal_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer(manager):\n"
                            "    import package_a.service as service\n"
                            "    while (caller := lambda: service.target()):\n"
                            f"{terminal_block}"
                            "        import package_b.service as service\n"
                            "    return caller\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target_a",
                            r"package_a/service\.py$",
                        ),
                        self._function_layer(
                            "target_b",
                            r"package_b/service\.py$",
                        ),
                        self._function_name_layer("outer", r"^outer$"),
                    ],
                    ruleset={
                        "outer": {
                            "disallow_layer_dependencies": [
                                "target_a",
                                "target_b",
                            ]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.parent.name
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    },
                    {"package_a"},
                )

    def test_lambda_sees_later_tuple_named_expression(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    caller, _ = (\n"
                    "        lambda: service.target(),\n"
                    "        (service := object()),\n"
                    "    )\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            [
                violation
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            ],
            [],
        )

    def test_terminal_with_body_does_not_fall_through(self):
        variants = (("def", "with"), ("async def", "async with"))
        for function_keyword, with_keyword in variants:
            with self.subTest(with_keyword=with_keyword):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            f"{function_keyword} outer(condition, manager):\n"
                            "    import package_a.service as service\n"
                            "    if condition:\n"
                            f"        {with_keyword} manager:\n"
                            "            return None\n"
                            "    else:\n"
                            "        import package_b.service as service\n"
                            "    service.target()\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target_a",
                            r"package_a/service\.py$",
                        ),
                        self._function_layer(
                            "target_b",
                            r"package_b/service\.py$",
                        ),
                        self._function_name_layer("outer", r"^outer$"),
                    ],
                    ruleset={
                        "outer": {
                            "disallow_layer_dependencies": [
                                "target_a",
                                "target_b",
                            ]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.parent.name
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    },
                    {"package_b"},
                )

    def test_deferred_function_flow_does_not_escape_scope(self):
        helper_bodies = {
            "return": "            return None\n",
            "raise": "            raise RuntimeError\n",
            "break": "            while True:\n                break\n",
            "continue": "            while True:\n                continue\n",
        }
        for terminal_type, helper_body in helper_bodies.items():
            with self.subTest(terminal_type=terminal_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            "    import package_a.service as service\n"
                            "    try:\n"
                            "        def helper():\n"
                            "            import package_b.service as service\n"
                            f"{helper_body}"
                            "    finally:\n"
                            "        def caller():\n"
                            "            service.target()\n"
                            "        return caller\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target_a",
                            r"package_a/service\.py$",
                        ),
                        self._function_layer(
                            "target_b",
                            r"package_b/service\.py$",
                        ),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {
                            "disallow_layer_dependencies": [
                                "target_a",
                                "target_b",
                            ]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.parent.name
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    },
                    {"package_a"},
                )

    def test_nested_potential_exception_reaches_handler_state(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    try:\n"
                    "        if True:\n"
                    "            import package_b.service as service\n"
                    "            1 / 0\n"
                    "    except Exception:\n"
                    "        def caller():\n"
                    "            service.target()\n"
                    "        return caller\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a", "package_b"},
        )

    def test_closure_ignores_try_handler_after_unconditional_break(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    while (caller := lambda: service.target()):\n"
                    "        try:\n"
                    "            break\n"
                    "        except Exception:\n"
                    "            pass\n"
                    "        import package_b.service as service\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_closure_sees_for_body_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    for caller in [lambda: service.target()]:\n"
                    "        import package_b.service as service\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_closure_sees_with_body_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(manager):\n"
                    "    import package_a.service as service\n"
                    "    with manager(caller := lambda: service.target()):\n"
                    "        import package_b.service as service\n"
                    "    return caller\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {
                    "disallow_layer_dependencies": ["target_a", "target_b"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    @unittest.skipUnless(hasattr(ast, "Match"), "requires Python 3.10")
    def test_closure_sees_exhaustive_match_rebinding(self):
        sources = {
            "subject": (
                "    match (caller := lambda: service.target()):\n"
                "        case _:\n"
                "            import package_b.service as service\n"
            ),
            "guard": (
                "    match object():\n"
                "        case _ if (caller := lambda: service.target()):\n"
                "            import package_b.service as service\n"
            ),
        }
        for closure_position, match_source in sources.items():
            with self.subTest(closure_position=closure_position):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            "    import package_a.service as service\n"
                            f"{match_source}"
                            "    return caller\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target_a",
                            r"package_a/service\.py$",
                        ),
                        self._function_layer(
                            "target_b",
                            r"package_b/service\.py$",
                        ),
                        self._function_name_layer("outer", r"^outer$"),
                    ],
                    ruleset={
                        "outer": {
                            "disallow_layer_dependencies": [
                                "target_a",
                                "target_b",
                            ]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.parent.name
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    },
                    {"package_b"},
                )

    def test_returning_rebinding_branch_does_not_reach_closure(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer(condition):\n"
                    "    import package_a.service as service\n"
                    "    def caller():\n"
                    "        service.target()\n"
                    "    if condition:\n"
                    "        import package_b.service as service\n"
                    "        return None\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_conditional_expression_rebinding_keeps_possible_import(self):
        expressions = {
            "if_expression": "(service := object()) if condition else None",
            "empty_comprehension": "[service := object() for _ in ()]",
            "short_circuited_compare": "0 > 1 < (service := object())",
        }
        for expression_type, expression in expressions.items():
            with self.subTest(expression_type=expression_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def caller(condition):\n"
                            "    import package_a.service as service\n"
                            f"    marker = {expression}\n"
                            "    service.target()\n"
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
                        "caller": {
                            "disallow_layer_dependencies": ["target"]
                        }
                    },
                )

                self.assertFalse(succeeded)
                self.assertEqual(
                    {
                        violation.dependency.depends_on_code_element.file.parent.name
                        for violation in violations
                        if violation.dependency.dependency_type == "function_call"
                    },
                    {"package_a"},
                )

    def test_nested_deterministic_rebinding_updates_closure(self):
        rebindings = {
            "assignment": "            service = object()\n",
            "import": "            import package_b.service as service\n",
        }
        for rebinding_type, rebinding in rebindings.items():
            with self.subTest(rebinding_type=rebinding_type):
                succeeded, violations = self._run_deply(
                    files={
                        "package_a/service.py": "def target():\n    pass\n",
                        "package_b/service.py": "def target():\n    pass\n",
                        "caller.py": (
                            "def outer():\n"
                            "    import package_a.service as service\n"
                            "    def caller():\n"
                            "        service.target()\n"
                            "    if True:\n"
                            "        if True:\n"
                            f"{rebinding}"
                            "    return caller\n"
                        ),
                    },
                    layers=[
                        self._function_layer(
                            "target_a",
                            r"package_a/service\.py$",
                        ),
                        self._function_layer(
                            "target_b",
                            r"package_b/service\.py$",
                        ),
                        self._function_name_layer("caller", r"^caller$"),
                    ],
                    ruleset={
                        "caller": {
                            "disallow_layer_dependencies": [
                                "target_a",
                                "target_b",
                            ]
                        }
                    },
                )

                call_targets = {
                    violation.dependency.depends_on_code_element.file.parent.name
                    for violation in violations
                    if violation.dependency.dependency_type == "function_call"
                }
                expected_targets = (
                    set() if rebinding_type == "assignment" else {"package_b"}
                )
                self.assertEqual(call_targets, expected_targets)

    def test_unreachable_relative_import_does_not_fail_analysis(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "package/__init__.py": "",
                "package/caller.py": (
                    "def caller():\n"
                    "    return None\n"
                    "    from ..missing import target\n"
                ),
            },
            layers=[
                self._function_name_layer("caller", r"^caller$")
            ],
            ruleset={},
            return_errors=True,
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])
        self.assertEqual(analysis_errors, [])

    def test_known_dead_branch_does_not_emit_import_dependency(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    if False:\n"
                    "        from package_a.service import target\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_unreachable_class_import_does_not_emit_dependency(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "class Caller:\n"
                    "    raise RuntimeError\n"
                    "    from package_a.service import target\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._element_layer("caller", r"caller\.py$", "class"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertTrue(succeeded)
        self.assertEqual(violations, [])

    def test_function_decorator_arguments_are_eager_dependencies(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "from package_a.service import target\n\n"
                    "def decorate(value):\n"
                    "    return lambda function: function\n\n"
                    "@decorate(target())\n"
                    "def caller():\n"
                    "    pass\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"target"},
        )

    def test_repeated_symbol_definitions_in_one_file_are_not_ambiguous(self):
        succeeded, violations, analysis_errors = self._run_deply(
            files={
                "service.py": "value = 1\nvalue = 2\n",
                "caller.py": (
                    "from service import value\n\n"
                    "def caller():\n"
                    "    return value\n"
                ),
            },
            layers=[
                self._element_layer("values", r"service\.py$", "variable"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {"disallow_layer_dependencies": ["values"]}
            },
            return_errors=True,
        )

        self.assertFalse(succeeded)
        self.assertEqual(analysis_errors, [])
        self.assertNotEqual(violations, [])

    def test_inner_caught_raise_does_not_reach_outer_handler(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "package_c/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def caller():\n"
                    "    import package_a.service as service\n"
                    "    try:\n"
                    "        try:\n"
                    "            import package_b.service as service\n"
                    "            raise RuntimeError\n"
                    "        except RuntimeError:\n"
                    "            pass\n"
                    "    except Exception:\n"
                    "        import package_c.service as service\n"
                    "    service.target()\n"
                ),
            },
            layers=[
                self._function_layer("target_a", r"package_a/service\.py$"),
                self._function_layer("target_b", r"package_b/service\.py$"),
                self._function_layer("target_c", r"package_c/service\.py$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": [
                        "target_a",
                        "target_b",
                        "target_c",
                    ]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_break_state_includes_finally_rebinding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    while True:\n"
                    "        try:\n"
                    "            break\n"
                    "        finally:\n"
                    "            import package_b.service as service\n"
                    "    def caller():\n"
                    "        service.target()\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_b"},
        )

    def test_immediate_lambda_call_uses_current_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    ((lambda: service.target())(), (service := object()))\n"
                ),
            },
            layers=[
                self._function_layer("target", r"package_a/service\.py$"),
                self._function_name_layer("outer", r"^outer$"),
            ],
            ruleset={
                "outer": {"disallow_layer_dependencies": ["target"]}
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_nested_function_call_before_rebinding_uses_current_binding(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    def caller():\n"
                    "        service.target()\n"
                    "    caller()\n"
                    "    import package_b.service as service\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a"},
        )

    def test_nested_function_calls_across_rebinding_keep_both_targets(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": "def target():\n    pass\n",
                "package_b/service.py": "def target():\n    pass\n",
                "caller.py": (
                    "def outer():\n"
                    "    import package_a.service as service\n"
                    "    def caller():\n"
                    "        service.target()\n"
                    "    caller()\n"
                    "    import package_b.service as service\n"
                    "    caller()\n"
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
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.file.parent.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"package_a", "package_b"},
        )

    def test_imported_class_alias_resolves_static_member(self):
        succeeded, violations = self._run_deply(
            files={
                "package_a/service.py": (
                    "class Service:\n"
                    "    @classmethod\n"
                    "    def target(cls):\n"
                    "        pass\n"
                ),
                "caller.py": (
                    "from package_a.service import Service as Alias\n\n"
                    "def caller():\n"
                    "    Alias.target()\n"
                ),
            },
            layers=[
                self._element_layer(
                    "service",
                    r"package_a/service\.py$",
                    "class",
                ),
                self._function_name_layer("target", r"^target$"),
                self._function_name_layer("caller", r"^caller$"),
            ],
            ruleset={
                "caller": {
                    "disallow_layer_dependencies": ["service", "target"]
                }
            },
        )

        self.assertFalse(succeeded)
        self.assertEqual(
            {
                violation.dependency.depends_on_code_element.name
                for violation in violations
                if violation.dependency.dependency_type == "function_call"
            },
            {"Service.target"},
        )

if __name__ == "__main__":
    unittest.main()
