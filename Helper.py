import sys

from model.UiDataModel import TermCode


def str_to_class(class_name):
    return getattr(sys.modules[__name__], class_name)


def traverse_tree(result, node):
    if children := node.get("children"):
        for child in children:
            if child.get("selectable"):
                result += [TermCode(**termCode) for termCode in child.get("termCodes")]
            traverse_tree(result, child)


def get_term_selectable_leaf_codes_from_ui_profile(profile):
    result = []
    if profile.get("selectable"):
        result += [TermCode(**termCode) for termCode in profile.get("termCodes")]
    traverse_tree(result, profile)
    return set(result)
