from app.events.parser import parse_event


def test_parse_push_event_extracts_branch_and_commit():
    parsed = parse_event(
        "push",
        {
            "ref": "refs/heads/main",
            "after": "abc123",
            "repository": {"full_name": "octocat/demo"},
        },
    )
    assert parsed.kind == "push"
    assert parsed.repository_full_name == "octocat/demo"
    assert parsed.branch == "main"
    assert parsed.commit_sha == "abc123"


def test_parse_pull_request_event_extracts_number_and_head():
    parsed = parse_event(
        "pull_request",
        {
            "action": "opened",
            "number": 12,
            "repository": {"full_name": "octocat/demo"},
            "pull_request": {
                "title": "Improve docs",
                "body": "Details",
                "state": "open",
                "html_url": "https://github.com/octocat/demo/pull/12",
                "head": {"ref": "feature/docs", "sha": "def456"},
                "user": {"login": "octocat"},
            },
        },
    )
    assert parsed.kind == "pull_request"
    assert parsed.number == 12
    assert parsed.branch == "feature/docs"
    assert parsed.commit_sha == "def456"
    assert parsed.title == "Improve docs"


def test_parse_workflow_run_event_extracts_conclusion():
    parsed = parse_event(
        "workflow_run",
        {
            "action": "completed",
            "repository": {"full_name": "octocat/demo"},
            "workflow_run": {
                "id": 88,
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "fedcba",
                "html_url": "https://github.com/octocat/demo/actions/runs/88",
            },
        },
    )
    assert parsed.kind == "workflow_run"
    assert parsed.external_id == 88
    assert parsed.conclusion == "failure"
    assert parsed.branch == "main"
    assert parsed.commit_sha == "fedcba"


def test_parse_release_event_extracts_tag_and_publish_time():
    parsed = parse_event(
        "release",
        {
            "action": "published",
            "repository": {"full_name": "octocat/demo"},
            "release": {
                "id": 99,
                "tag_name": "v1.2.0",
                "name": "Version 1.2.0",
                "body": "Highlights",
                "published_at": "2026-08-26T08:00:00Z",
                "html_url": "https://github.com/octocat/demo/releases/tag/v1.2.0",
            },
        },
    )
    assert parsed.kind == "release"
    assert parsed.external_id == 99
    assert parsed.tag_name == "v1.2.0"
    assert parsed.published_at == "2026-08-26T08:00:00Z"


def test_unknown_event_is_ignored():
    parsed = parse_event("star", {"repository": {"full_name": "octocat/demo"}})
    assert parsed.kind == "ignored"
