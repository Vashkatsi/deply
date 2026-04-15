import ast
from typing import Dict, Optional


def get_import_aliases(tree: ast.AST) -> Dict[str, str]:
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                asname = alias.asname or alias.name
                aliases[asname] = name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                full_name = f"{module}.{alias.name}" if module else alias.name
                asname = alias.asname or alias.name
                aliases[asname] = full_name
    return aliases


def get_base_name(node: ast.AST, import_aliases: Dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return import_aliases.get(node.id, node.id)
    elif isinstance(node, ast.Attribute):
        value = get_base_name(node.value, import_aliases)
        return f"{value}.{node.attr}" if value else node.attr
    else:
        return ''


def get_decorator_name(decorator_node: ast.AST) -> Optional[str]:
    if isinstance(decorator_node, ast.Name):
        return decorator_node.id
    elif isinstance(decorator_node, ast.Attribute):
        attr_parts = []
        current: ast.AST = decorator_node
        # Unroll attributes: @mod.sub.decorator
        while isinstance(current, ast.Attribute):
            attr_parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            attr_parts.append(current.id)
        if attr_parts:
            return ".".join(reversed(attr_parts))
        return None
    elif isinstance(decorator_node, ast.Call):
        return get_decorator_name(decorator_node.func)
    else:
        # Complex or unsupported decorator
        return None


def get_annotation_name(annotation_node: Optional[ast.AST], import_aliases: Dict[str, str]) -> Optional[str]:
    if annotation_node is None:
        return None

    if isinstance(annotation_node, ast.Name):
        return import_aliases.get(annotation_node.id, annotation_node.id)

    elif isinstance(annotation_node, ast.Attribute):
        parts = []
        current: ast.AST = annotation_node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(import_aliases.get(current.id, current.id))
        return ".".join(reversed(parts)) if parts else None

    elif isinstance(annotation_node, ast.Subscript):
        # Handle generics like List[str]
        base_name = get_annotation_name(annotation_node.value, import_aliases)
        slice_node = annotation_node.slice
        # ast.Index was removed in Python 3.9, slice.value might be directly the node in newer Python versions
        element_node = slice_node.value if hasattr(slice_node, 'value') else slice_node
        sub_name = get_annotation_name(element_node, import_aliases)
        if base_name is None or sub_name is None:
            return None
        return f"{base_name}[{sub_name}]"

    # Unknown or complex annotation
    return None


def set_ast_parents(root: ast.AST):
    for child in ast.iter_child_nodes(root):
        setattr(child, "parent", root)
        set_ast_parents(child)
