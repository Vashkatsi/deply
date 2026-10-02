import argparse
import ast
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from deply.code_analyzer import CodeAnalyzer
from deply.collectors.directory_collector import DirectoryCollector
from deply.collectors.file_regex_collector import FileRegexCollector
from deply.deply_runner import DeplyRunner


class TestModuleAwareDependencyResolution(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)

    def write_files(self, sources):
        files = []
        for relative_path, source in sources.items():
            file_path = self.root / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
            files.append(file_path)
        return files

    def analyze(self, sources, collector_type="directory", regex=r".*\.py$", roots=None,
                expected_errors=False, excluded_files=()):
        files = self.write_files(sources)
        files = [file_path for file_path in files if str(file_path.relative_to(self.root)) not in excluded_files]
        analysis_paths = roots or [self.root]
        paths = [str(root) for root in analysis_paths]
        collector = (
            DirectoryCollector({"directories": ["."]}, paths, [])
            if collector_type == "directory"
            else FileRegexCollector({"regex": regex}, paths, [])
        )
        elements = set()
        for file_path in files:
            elements.update(collector.match_in_file(ast.parse(file_path.read_text()), file_path))
        dependencies = []
        errors = CodeAnalyzer(
            elements, dependencies.append, analysis_paths=analysis_paths, files=files,
        ).analyze()
        self.assertEqual(bool(errors), expected_errors, errors)
        return (dependencies, errors) if expected_errors else dependencies

    def targets(self, dependencies, source_name, dependency_type=None, uses_only=False):
        return {
            (str(dependency.depends_on_code_element.file.relative_to(self.root)),
             dependency.depends_on_code_element.name)
            for dependency in dependencies
            if dependency.code_element.name == source_name
            and (dependency_type is None or dependency.dependency_type == dependency_type)
            and (not uses_only or dependency.dependency_type not in {"import", "import_from"})
        }

    def test_django_attribute_chain_resolves_for_variables_and_functions(self):
        sources = {
            "app/__init__.py": "",
            "app/models.py": "class Project: pass",
            "app/views.py": """
                from . import models
                queryset = models.Project.objects.all()
                def projects():
                    return models.Project.objects.all()
            """,
        }
        for collector_type in ("directory", "file_regex"):
            with self.subTest(collector=collector_type):
                dependencies = self.analyze(sources, collector_type)
                for owner in ("queryset", "projects"):
                    self.assertEqual(
                        self.targets(dependencies, owner, "function_call"),
                        {("app/models.py", "Project")},
                    )

    def test_import_bindings_resolve_aliases_and_relative_modules(self):
        imports_and_calls = (
            ("import app.models", "app.models.Project()"),
            ("import app.models as records", "records.Project()"),
            ("from app import models as records", "records.Project()"),
            ("from . import models as records", "records.Project()"),
            ("from app.models import Project as Model", "Model()"),
            ("from .models import Project as Model", "Model()"),
        )
        for import_statement, expression in imports_and_calls:
            with self.subTest(import_statement=import_statement):
                dependencies = self.analyze({
                    "app/__init__.py": "",
                    "app/models.py": "class Project: pass",
                    "other/models.py": "class Project: pass",
                    "app/views.py": f"{import_statement}\ndef create():\n    return {expression}\n",
                })
                self.assertEqual(
                    self.targets(dependencies, "create", "function_call"),
                    {("app/models.py", "Project")},
                )

    def test_module_import_and_symbol_import_have_distinct_targets(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass\nclass Account: pass",
            "module_user.py": "import models\ndef module_user(): pass",
            "symbol_user.py": "from models import Project\ndef symbol_user(): pass",
        })
        self.assertEqual(
            self.targets(dependencies, "module_user", "import"),
            {("models.py", "Project"), ("models.py", "Account")},
        )
        self.assertEqual(
            self.targets(dependencies, "symbol_user", "import_from"),
            {("models.py", "Project")},
        )

    def test_multiple_modules_in_one_import_keep_each_direct_target(self):
        dependencies = self.analyze({
            "app/models.py": "class Project: pass",
            "app/services.py": "class Service: pass",
            "views.py": "import app.models, app.services\ndef create():\n    return app.models.Project(), app.services.Service()",
        })
        expected_targets = {("app/models.py", "Project"), ("app/services.py", "Service")}
        self.assertEqual(self.targets(dependencies, "create", "import"), expected_targets)
        self.assertEqual(self.targets(dependencies, "create", "function_call"), expected_targets)

    def test_explicit_submodule_imports_override_package_placeholders(self):
        import_statements = (
            "import app.models",
            "import app.models\nimport app.services",
            "import app.models, app.services",
        )
        for import_statement in import_statements:
            with self.subTest(import_statement=import_statement):
                include_service = "services" in import_statement
                expression = "app.models.Project()" + (", app.services.Service()" if include_service else "")
                dependencies = self.analyze({
                    "app/__init__.py": "models = None\nservices = None",
                    "app/models.py": "class Project: pass",
                    "app/services.py": "class Service: pass",
                    "views.py": f"{import_statement}\ndef create():\n    return {expression}",
                })
                expected_targets = {("app/models.py", "Project")}
                if include_service:
                    expected_targets.add(("app/services.py", "Service"))
                self.assertEqual(self.targets(dependencies, "create", "function_call"), expected_targets)

    def test_module_import_includes_collected_private_symbols(self):
        dependencies = self.analyze({
            "models.py": "class _Project: pass",
            "views.py": "import models\ndef create(): pass",
        })
        self.assertEqual(self.targets(dependencies, "create", "import"), {("models.py", "_Project")})

    def test_package_access_requires_imported_or_reexported_submodules(self):
        project_target = {("app/models.py", "Project")}
        cases = (
            ("", "import app", "return app.models.Project()", set()),
            ("", "import app.models", "return app.models.Project(), app.other.Other()", project_target),
            ("", "from app import models", "return models.Project()", project_target),
            ("from . import models", "import app", "return app.models.Project()", project_target),
            ("", "from app import models\nimport app", "return app.models.Project()", project_target),
            ("", "from app.models import Project\nimport app", "return app.models.Project()", project_target),
            ("", "from app import models", "import app\n    return app.models.Project()", project_target),
            ("", "import app.models", "import app\n    return app.models.Project()", project_target),
        )
        for package_source, import_statement, function_body, expected_targets in cases:
            with self.subTest(package_source=package_source, import_statement=import_statement):
                dependencies = self.analyze({
                    "app/__init__.py": package_source,
                    "app/models.py": "class Project: pass",
                    "app/other.py": "class Other: pass",
                    "views.py": f"{import_statement}\ndef create():\n    {function_body}",
                })
                self.assertEqual(self.targets(dependencies, "create", "function_call"), expected_targets)

    def test_dynamic_package_exports_are_not_guessed(self):
        for import_statement, expression, expected_targets in (
            ("from app import models", "models.Project()", set()),
            ("import app.models", "app.models.Project()", {("app/models.py", "Project")}),
        ):
            with self.subTest(import_statement=import_statement):
                dependencies = self.analyze({
                    "app/__init__.py": "def __getattr__(name): return object()",
                    "app/models.py": "class Project: pass",
                    "views.py": f"{import_statement}\ndef create():\n    return {expression}",
                })
                self.assertEqual(self.targets(dependencies, "create", "function_call"), expected_targets)

    def test_rebound_alias_in_single_from_import_uses_last_symbol(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass\nclass Account: pass",
            "views.py": "from models import Project as Model, Account as Model\ndef create():\n    return Model()",
        })
        self.assertEqual(
            self.targets(dependencies, "create", "import_from"),
            {("models.py", "Project"), ("models.py", "Account")},
        )
        self.assertEqual(
            self.targets(dependencies, "create", "function_call"),
            {("models.py", "Account")},
        )

    def test_unimported_and_external_names_do_not_match_other_modules(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "unimported.py": "def create_unimported():\n    return Project()",
            "external.py": "from external_library import Project\ndef create_external():\n    return Project()",
        })
        self.assertEqual(self.targets(dependencies, "create_unimported"), set())
        self.assertEqual(self.targets(dependencies, "create_external"), set())

    def test_package_reexport_resolves_through_uncollected_file(self):
        dependencies = self.analyze({
            "app/__init__.py": "from .models import Project as PublicProject",
            "app/models.py": "class Project: pass",
            "views.py": "from app import PublicProject as Model\ndef create():\n    return Model()",
        }, "file_regex", regex=r"(app/models|views)\.py$")
        self.assertEqual(
            self.targets(dependencies, "create", "function_call"),
            {("app/models.py", "Project")},
        )

    def test_local_import_does_not_leak_to_sibling_functions(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "views.py": """
                def importing():
                    from models import Project as Model
                    return Model()
                def sibling():
                    return Model()
            """,
        })
        self.assertEqual(
            self.targets(dependencies, "importing", "import_from"),
            {("models.py", "Project")},
        )
        self.assertEqual(
            self.targets(dependencies, "importing", "function_call"),
            {("models.py", "Project")},
        )
        self.assertEqual(self.targets(dependencies, "sibling"), set())

    def test_parameters_and_assignments_shadow_imported_symbols(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "views.py": """
                from models import Project
                import models as records
                def parameter(Project):
                    return Project()
                def assigned():
                    Project = object()
                    return Project()
                def module_parameter(records):
                    return records.Project()
                def module_assigned():
                    records = object()
                    return records.Project()
                def original():
                    return Project()
            """,
        })
        for owner in ("parameter", "assigned", "module_parameter", "module_assigned"):
            with self.subTest(owner=owner):
                self.assertNotIn(("models.py", "Project"), self.targets(dependencies, owner, uses_only=True))
        self.assertEqual(
            self.targets(dependencies, "original", "function_call"),
            {("models.py", "Project")},
        )

    def test_nested_functions_inherit_imports_and_methods_skip_class_bindings(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "other.py": "class Project: pass",
            "views.py": """
                from models import Project
                class Container:
                    Project = object()
                    def create(self):
                        return Project()
                def outer():
                    from other import Project
                    def inner():
                        return Project()
                    return inner()
                def sibling():
                    return Project()
            """,
        })
        self.assertEqual(
            self.targets(dependencies, "Container.create", "function_call"),
            {("models.py", "Project")},
        )
        self.assertEqual(
            self.targets(dependencies, "outer.inner", "function_call"),
            {("other.py", "Project")},
        )
        self.assertEqual(
            self.targets(dependencies, "sibling", "function_call"),
            {("models.py", "Project")},
        )

    def test_inheritance_decorators_and_annotations_use_same_alias_resolution(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass\ndef decorate(value): return value",
            "views.py": """
                from models import Project as Model, decorate as wrapped
                @wrapped
                class Derived(Model):
                    pass
                @wrapped
                def create(value: Model) -> Model:
                    return Model()
            """,
        })
        expected_types = (
            ("Derived", "class_inheritance", "Project"),
            ("Derived", "decorator", "decorate"),
            ("create", "decorator", "decorate"),
            ("create", "type_annotation", "Project"),
            ("create", "function_call", "Project"),
        )
        for owner, dependency_type, target in expected_types:
            with self.subTest(owner=owner, dependency_type=dependency_type):
                self.assertEqual(
                    self.targets(dependencies, owner, dependency_type),
                    {("models.py", target)},
                )

    def test_annotation_only_binding_preserves_imports_outside_functions(self):
        scope_cases = (
            ("from models import Project\nProject: type\ndef create():\n    return Project()", "create", True),
            ("from models import Project\nclass Container:\n    Project: type\n    value = Project()", "Container", True),
            ("from models import Project\ndef create():\n    Project: type\n    return Project()", "create", False),
        )
        for source, owner, imported_target_expected in scope_cases:
            with self.subTest(source=source):
                dependencies = self.analyze({"models.py": "class Project: pass", "views.py": source})
                self.assertEqual(
                    ("models.py", "Project") in self.targets(dependencies, owner, "function_call"),
                    imported_target_expected,
                )

    def test_definition_headers_use_enclosing_scope_before_parameter_bindings(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass\ndef decorate(value): return value",
            "views.py": """
                from models import Project as Model, decorate as wrapped
                @wrapped
                def create(Model: Model = Model(), wrapped=wrapped) -> Model:
                    return Model()
                class Model(Model):
                    pass
            """,
        })
        for owner, dependency_type, target in (
            ("create", "decorator", "decorate"),
            ("Model", "class_inheritance", "Project"),
        ):
            with self.subTest(owner=owner, dependency_type=dependency_type):
                self.assertEqual(self.targets(dependencies, owner, dependency_type), {("models.py", target)})
        annotation_target = ("views.py", "Model") if sys.version_info >= (3, 14) else ("models.py", "Project")
        self.assertEqual(self.targets(dependencies, "create", "type_annotation"), {annotation_target})
        imported_calls = [
            dependency.line for dependency in dependencies
            if dependency.code_element.name == "create"
            and dependency.depends_on_code_element.file == self.root / "models.py"
            and dependency.dependency_type == "function_call"
        ]
        self.assertEqual(imported_calls, [3])

    def test_comprehension_and_lambda_bindings_do_not_leak(self):
        expressions = (
            "[Project() for Project in values]",
            "(lambda Project: Project())(None)",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                dependencies = self.analyze({
                    "models.py": "class Project: pass",
                    "views.py": f"from models import Project\ndef create(values):\n    {expression}\n    return Project()",
                })
                imported_calls = [
                    dependency.line for dependency in dependencies
                    if dependency.code_element.name == "create"
                    and dependency.depends_on_code_element.file == self.root / "models.py"
                    and dependency.dependency_type == "function_call"
                ]
                self.assertEqual(imported_calls, [4])

    @unittest.skipUnless(sys.version_info >= (3, 12), "generic declarations require Python 3.12")
    def test_generic_type_parameters_shadow_imports_in_annotation_scopes(self):
        sources_and_owners = (
            ("def create[Project](value: Project) -> Project:\n    return Project()", ("create",)),
            ("class Container[Project](Project):\n"
             "    def create(self, value: Project) -> Project:\n"
             "        return Project()", ("Container", "Container.create")),
        )
        for source, owners in sources_and_owners:
            with self.subTest(source=source):
                dependencies = self.analyze({
                    "models.py": "class Project: pass",
                    "views.py": f"from models import Project\n{source}",
                })
                for owner in owners:
                    self.assertNotIn(("models.py", "Project"), self.targets(dependencies, owner, uses_only=True))
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "views.py": "from models import Project\n@Project\ndef create[Project](value=Project):\n    return Project()",
        })
        self.assertEqual(self.targets(dependencies, "create", "decorator"), {("models.py", "Project")})
        imported_uses = {
            dependency.line for dependency in dependencies
            if dependency.code_element.name == "create"
            and dependency.depends_on_code_element.file == self.root / "models.py"
            and dependency.dependency_type == "name_load"
        }
        self.assertEqual(imported_uses, {2, 3})

    def test_deferred_forward_annotations_resolve_later_and_self_definitions(self):
        cases = [
            ("def create() -> 'Project': pass\nclass Project: pass", "create"),
            ("class Project:\n    def clone(self) -> 'Project': pass", "Project.clone"),
            ("from __future__ import annotations\ndef create() -> Project: pass\nclass Project: pass", "create"),
        ]
        if sys.version_info >= (3, 14):
            cases.append(("def create() -> Project: pass\nclass Project: pass", "create"))
        for source, owner in cases:
            with self.subTest(source=source):
                dependencies = self.analyze({"views.py": source})
                self.assertEqual(self.targets(dependencies, owner, "type_annotation"), {("views.py", "Project")})

    def test_global_and_nonlocal_import_rebindings_resolve_inside_their_scope(self):
        dependencies = self.analyze({
            "models.py": "class Project: pass",
            "other.py": "class Project: pass",
            "views.py": """
                from models import Project
                def global_rebinding():
                    global Project
                    from other import Project
                    return Project()
                def outer():
                    from models import Project
                    def rebinding():
                        nonlocal Project
                        from other import Project
                        return Project()
                    return rebinding()
            """,
        })
        for owner in ("global_rebinding", "outer.rebinding"):
            self.assertEqual(self.targets(dependencies, owner, "function_call"), {("other.py", "Project")})

    def test_cyclic_reexports_terminate_without_global_name_fallback(self):
        dependencies = self.analyze({
            "app/__init__.py": "from .first import Project",
            "app/first.py": "from .second import Project",
            "app/second.py": "from .first import Project",
            "models.py": "class Project: pass",
            "views.py": "from app import Project\ndef create():\n    return Project()",
        })
        self.assertEqual(self.targets(dependencies, "create"), set())

    def test_src_root_and_namespace_package_are_resolved_without_config_changes(self):
        sources = {
            "src/app/models.py": "class Project: pass",
            "src/app/views.py": "from .models import Project\ndef create():\n    return Project()",
        }
        for root in (self.root, self.root / "src"):
            with self.subTest(root=root):
                dependencies = self.analyze(sources, roots=[root])
                self.assertEqual(
                    self.targets(dependencies, "create", "function_call"),
                    {("src/app/models.py", "Project")},
                )

    def test_overlapping_roots_keep_module_identity_stable(self):
        sources = {
            "app/__init__.py": "",
            "app/models.py": "class Project: pass",
            "app/views.py": "from app.models import Project\ndef create():\n    return Project()",
        }
        for roots in ([self.root], [self.root, self.root / "app"]):
            with self.subTest(roots=roots):
                dependencies = self.analyze(sources, roots=roots)
                self.assertEqual(
                    self.targets(dependencies, "create", "function_call"),
                    {("app/models.py", "Project")},
                )

    def test_multiple_roots_do_not_arbitrarily_resolve_ambiguous_module(self):
        dependencies, errors = self.analyze({
            "first/models.py": "class Project: pass",
            "second/models.py": "class Project: pass",
            "first/views.py": "from models import Project\ndef create():\n    return Project()",
        }, roots=[self.root / "first", self.root / "second"], expected_errors=True)
        self.assertEqual(self.targets(dependencies, "create"), set())
        self.assertTrue(any("ambiguous module 'models'" in error for error in errors))
        for candidate in (self.root / "first/models.py", self.root / "second/models.py"):
            self.assertTrue(any(str(candidate) in error for error in errors))

    def test_regular_packages_limit_submodules_to_their_directory(self):
        scenarios = (
            ("regular_first", "first", "second", False),
            ("regular_second", "second", "first", False),
            ("regular_owns_submodule", "first", "second", True),
        )
        for scenario, regular_root, namespace_root, owns_submodule in scenarios:
            sources = {
                f"{scenario}/{regular_root}/app/__init__.py": "",
                f"{scenario}/{namespace_root}/app/b.py": "class B: pass",
                f"{scenario}/first/views.py": "import app.b\ndef create():\n    return app.b.B()",
            }
            expected_targets = set()
            if owns_submodule:
                regular_submodule = f"{scenario}/{regular_root}/app/b.py"
                sources[regular_submodule] = "class B: pass"
                expected_targets.add((regular_submodule, "B"))
            roots = [self.root / scenario / "first", self.root / scenario / "second"]
            for ordered_roots in (roots, list(reversed(roots))):
                with self.subTest(scenario=scenario, roots=ordered_roots):
                    dependencies = self.analyze(sources, roots=ordered_roots)
                    self.assertEqual(self.targets(dependencies, "create", "function_call"), expected_targets)
                    self.assertEqual(self.targets(dependencies, "create", "import"), expected_targets)

    def test_multiple_regular_packages_report_ambiguity(self):
        dependencies, errors = self.analyze({
            "first/app/__init__.py": "class First: pass",
            "second/app/__init__.py": "class Second: pass",
            "first/views.py": "import app\ndef create(): pass",
        }, roots=[self.root / "first", self.root / "second"], expected_errors=True)
        self.assertEqual(self.targets(dependencies, "create"), set())
        self.assertTrue(any("ambiguous module 'app'" in error for error in errors))
        for candidate in (self.root / "first/app/__init__.py", self.root / "second/app/__init__.py"):
            self.assertTrue(any(str(candidate) in error for error in errors))

    def test_excluded_initializer_still_defines_regular_package_boundary(self):
        for included_descendant in (False, True):
            with self.subTest(included_descendant=included_descendant):
                sources = {
                    "first/app/__init__.py": "",
                    "second/app/b.py": "class B: pass",
                    "first/views.py": "import app.b\ndef create():\n    return app.b.B()",
                }
                if included_descendant:
                    sources["first/app/a.py"] = "class A: pass"
                dependencies = self.analyze(sources, roots=[self.root / "first", self.root / "second"],
                                            excluded_files=["first/app/__init__.py"])
                self.assertEqual(self.targets(dependencies, "create"), set())

    def test_existing_yaml_config_detects_issue_through_runner(self):
        self.write_files({
            "app/__init__.py": "",
            "app/models.py": "class Project: pass",
            "app/views.py": "from . import models\nqueryset = models.Project.objects.all()",
        })
        config_path = self.root / "deply.yaml"
        config_path.write_text(yaml.safe_dump({"deply": {
            "paths": [str(self.root)],
            "layers": [
                {"name": "models", "collectors": [{"type": "file_regex", "regex": r"app/models\.py$"}]},
                {"name": "views", "collectors": [{"type": "file_regex", "regex": r"app/views\.py$"}]},
            ],
            "ruleset": {"views": {"disallow_layer_dependencies": ["models"]}},
        }}), encoding="utf-8")
        runner = DeplyRunner(argparse.Namespace(
            config=str(config_path), parallel=None, report_format="text", output=None,
            mermaid=False, max_violations=0,
        ))
        with patch.object(runner, "output_report"):
            self.assertFalse(runner.run())
        self.assertEqual(runner.analysis_errors, [])
        self.assertTrue(any(violation.element_name == "queryset" for violation in runner.violations))

    def test_existing_yaml_config_reports_ambiguous_modules_as_incomplete(self):
        self.write_files({
            "first/models.py": "class Project: pass",
            "second/models.py": "class Project: pass",
            "first/views.py": "from models import Project\ndef create():\n    return Project()",
        })
        config_path = self.root / "deply.yaml"
        config_path.write_text(yaml.safe_dump({"deply": {
            "paths": [str(self.root / "first"), str(self.root / "second")],
            "layers": [{"name": "application", "collectors": [{"type": "directory", "directories": ["."]}]}],
            "ruleset": {},
        }}), encoding="utf-8")
        runner = DeplyRunner(argparse.Namespace(
            config=str(config_path), parallel=None, report_format="text", output=None,
            mermaid=False, max_violations=0,
        ))
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            self.assertFalse(runner.run())
        self.assertIn("Incomplete analysis", stderr.getvalue())
        self.assertTrue(any("ambiguous module 'models'" in error for error in runner.analysis_errors))


if __name__ == "__main__":
    unittest.main()
