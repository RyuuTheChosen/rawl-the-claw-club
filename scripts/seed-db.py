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
    from rawl.gateway.auth import derive_api_key, hash_api_key

    async with async_session_factory() as db:
        # Create test users with API keys
        wallets = [
            "TestWallet1111111111111111111111111111111111",
            "TestWallet2222222222222222222222222222222222",
            "TestWallet3333333333333333333333333333333333",
        ]

        users = []
        api_keys = {}
        for wallet in wallets:
            api_key = derive_api_key(wallet)
            user = User(
                wallet_address=wallet,
                api_key_hash=hash_api_key(api_key),
            )
            db.add(user)
            users.append(user)
            api_keys[wallet] = api_key

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
        print()
        print("API Keys for gateway testing:")
        for wallet, key in api_keys.items():
            print(f"  {wallet[:20]}...: {key}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
