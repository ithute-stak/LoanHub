"""Avoid re-opening websocket and refetching all datasets on route navigation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
SOURCE = (ROOT / "provider" / "realtimeProvider.tsx").read_text()


def test_route_transition_does_not_restart_websocket():
    assert "const pathnameRef = useRef(pathname);" in SOURCE
    assert "pathnameRef.current = pathname;" in SOURCE
    assert "shouldRefreshRouteForCommit(pathnameRef.current, detailForDispatch)" in SOURCE

    # WebSocket effect controls subscriptions and connection lifetime. The path
    # may be used via the ref but never as a reconnect dependency.
    effect = SOURCE[SOURCE.index("    useEffect(() => {"):SOURCE.index("    const subscribe = useCallback(")]
    deps = effect.rsplit("    ],", 1)[0].rsplit("    }, [", 1)[1]
    assert "pathname," not in deps
    assert "activeMembership?.branch_id" in deps
    assert "activeRole," in deps
    assert "accessToken," in deps


def test_websocket_scope_is_branch_aware():
    socket_key = SOURCE.split("const socketKey = [", 1)[1].split("].join", 1)[0]
    assert "activeMembership?.branch_id" in socket_key
