def validate_jdm(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    if 'nodes' not in data:
        return False
    if 'edges' not in data:
        return False
    return True


def rule_children(rule: dict) -> list[str]:
    return [
        node['content']['key']
        for node in rule['nodes']
        if node['type'] == 'decisionNode'
    ]
