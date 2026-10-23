import asyncio

from app.engine.live_state import match_states
from app.ws.manager import manager
from scripts.demo_match import create_demo


def test_slow_client_is_bounded_and_does_not_block_other_clients(db):
    demo = create_demo(db)
    state = match_states.get(demo.match_id)

    async def scenario():
        slow = manager.subscribe(demo.match_id, 'slow')
        fast = manager.subscribe(demo.match_id, 'fast')
        other = manager.subscribe('another-match', 'other')
        try:
            for revision in range(2, 20):
                frame = state.model_copy(deep=True)
                frame.revision = revision
                await asyncio.to_thread(manager.broadcast, frame)
                received = await asyncio.wait_for(fast.queue.get(), timeout=1)
                assert received['state']['revision'] == revision
            assert slow.queue.qsize() == 1
            assert (await slow.queue.get())['state']['revision'] == 19
            assert other.queue.empty()
            manager.revoke_session('slow')
            manager.broadcast(state)
            await asyncio.sleep(0)
            assert (await slow.queue.get())['type'] == 'revoked'
        finally:
            for subscriber in (slow, fast, other):
                manager.unsubscribe(subscriber)
    asyncio.run(scenario())
