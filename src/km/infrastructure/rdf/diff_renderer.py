"""Semantic diff blocks for MR review documents (spec §7.2)."""


def render_semantic_diff(diff_insertions: str, diff_deletions: str = "") -> str:
    lines = ["```diff", "@@ exports/main.ttl @@"]
    for line in diff_deletions.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(f"-{stripped}")
    for line in diff_insertions.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(f"+{stripped}")
    lines.append("```")
    return "\n".join(lines)
