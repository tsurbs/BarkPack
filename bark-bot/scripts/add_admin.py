import asyncio
import os
import sys
import uuid
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the root project directory to the path so we can import 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.models import DBRole, DBUserAuth, DBUserRole, Base
from app.db.session import engine, DATABASE_URL

async def add_admin(email: str):
    print(f"Connecting to database to add admin: {email}")
    
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    
    async with async_session() as session:
        # 1. Ensure 'admin' role exists
        result = await session.execute(select(DBRole).where(DBRole.name == "admin"))
        admin_role = result.scalar_one_or_none()
        
        if not admin_role:
            print("Creating 'admin' role...")
            admin_role = DBRole(id=str(uuid.uuid4()), name="admin", description="Administrator with full access")
            session.add(admin_role)
            await session.flush()
        else:
            print("Found existing 'admin' role.")

        # 2. Find user by email
        result = await session.execute(select(DBUserAuth).where(DBUserAuth.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"Error: User with email '{email}' not found. Please sign up first.")
            return

        # 3. Assign role
        result = await session.execute(
            select(DBUserRole).where(
                (DBUserRole.user_id == user.id) & (DBUserRole.role_id == admin_role.id)
            )
        )
        existing_mapping = result.scalar_one_or_none()
        
        if existing_mapping:
            print(f"User '{email}' is already an admin.")
        else:
            print(f"Assigning 'admin' role to user '{email}'...")
            new_role_mapping = DBUserRole(
                id=str(uuid.uuid4()),
                user_id=user.id,
                role_id=admin_role.id
            )
            session.add(new_role_mapping)
            await session.commit()
            print(f"Successfully added admin: {email} ✅")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_admin.py <email>")
        sys.exit(1)
    
    email_to_add = sys.argv[1]
    asyncio.run(add_admin(email_to_add))
