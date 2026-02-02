import asyncio
from sqlalchemy import select
from clients.database import init_db, AsyncSessionLocal, UseCaseDB

async def seed_data():
    """
    Initial seed data for use cases.
    This should be run once to populate the database.
    """
    await init_db()
    
    use_cases = [
        {
            "id": 1,
            "name": "Squad Navigator",
            "uri_context": "squad-navigator",
            "title": "Squad Navigator",
            "description": "Welcome to Squad Navigator use case.",
            "details": "Navigate through your squads and manage team collaboration effectively."
        },
        {
            "id": 2,
            "name": "Chapter Explorer",
            "uri_context": "chapter-explorer",
            "title": "Chapter Explorer",
            "description": "Welcome to Chapter Explorer use case.",
            "details": "Explore chapters and discover insights across different organizational units."
        },
        {
            "id": 3,
            "name": "Guild Convener",
            "uri_context": "guild-convener",
            "title": "Guild Convener",
            "description": "Welcome to Guild Convener use case.",
            "details": "Convene guilds and facilitate cross-functional collaboration."
        }
    ]
    
    async with AsyncSessionLocal() as session:
        # Check if data already exists
        result = await session.execute(select(UseCaseDB))
        existing = result.scalars().first()
        
        if not existing:
            for uc_data in use_cases:
                use_case = UseCaseDB(**uc_data)
                session.add(use_case)
            
            await session.commit()
            print("✓ Database seeded with use cases")
        else:
            print("✓ Database already contains data")

if __name__ == "__main__":
    asyncio.run(seed_data())
