"""Seed the database with test data for development."""

import asyncio
import uuid
import sys

sys.path.insert(0, "packages/backend/src")


async def seed():
    from rawl.db.session import async_session_factory, engine
    from rawl.db.models.user import User
    from rawl.db.models.fighter import Fighter
    from rawl.db.models.match import Match

    async with async_session_factory() as db:
        # Create test users
        users = []
        for i, wallet in enumerate([
            "TestWallet1111111111111111111111111111111111",
            "TestWallet2222222222222222222222222222222222",
            "TestWallet3333333333333333333333333333333333",
        ]):
            user = User(wallet_address=wallet)
            db.add(user)
            users.append(user)

        await db.flush()

        # Create test fighters
        fighters = []
        games = ["sfiii3n", "kof98", "tektagt"]
        for i, user in enumerate(users):
            for game in games:
                fighter = Fighter(
                    owner_id=user.id,
                    name=f"TestFighter-{user.wallet_address[:8]}-{game}",
                    game_id=game,
                    character="default",
                    model_path=f"models/test/{game}/{uuid.uuid4()}.zip",
                    elo_rating=1200.0 + (i * 50),
                    status="ready",
                )
                db.add(fighter)
                fighters.append(fighter)

        await db.flush()

        # Create a few test matches
        for game in games:
            game_fighters = [f for f in fighters if f.game_id == game]
            if len(game_fighters) >= 2:
                match = Match(
                    game_id=game,
                    fighter_a_id=game_fighters[0].id,
                    fighter_b_id=game_fighters[1].id,
                    status="open",
                    match_type="ranked",
                )
                db.add(match)

        await db.commit()
        print(f"Seeded {len(users)} users, {len(fighters)} fighters, {len(games)} matches")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
