"""
Database connection and utilities
Supports both local postgres (Docker) and Digital Ocean managed database
"""
import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse


def get_db_config():
    """Parse DATABASE_URL and return connection parameters"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Parse the URL
    result = urlparse(database_url)

    # Extract SSL mode from query parameters
    sslmode = 'prefer'  # default
    if result.query:
        params = dict(param.split('=') for param in result.query.split('&'))
        sslmode = params.get('sslmode', 'prefer')

    return {
        'host': result.hostname,
        'port': result.port or 5432,
        'database': result.path[1:],  # Remove leading slash
        'user': result.username,
        'password': result.password,
        'sslmode': sslmode
    }


def get_connection():
    """
    Get a database connection
    Works with both local postgres and Digital Ocean managed database
    """
    config = get_db_config()

    conn = psycopg2.connect(
        host=config['host'],
        port=config['port'],
        database=config['database'],
        user=config['user'],
        password=config['password'],
        sslmode=config['sslmode'],
        connect_timeout=10
    )

    return conn


@contextmanager
def get_db():
    """
    Context manager for database connections
    Automatically handles commit/rollback and connection cleanup

    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_query(query, params=None, fetch=True):
    """
    Execute a query and optionally fetch results

    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch: If True, return results; if False, return rowcount

    Returns:
        List of dicts (if fetch=True) or rowcount (if fetch=False)
    """
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)

        if fetch:
            return cursor.fetchall()
        else:
            return cursor.rowcount


def test_connection():
    """
    Test database connection
    Returns True if successful, raises exception otherwise
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise


# SQLAlchemy setup (optional, for ORM if needed later)
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    from sqlalchemy.ext.declarative import declarative_base

    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # SQLAlchemy engine
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL logging
        )

        # Session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Session = scoped_session(SessionLocal)

        # Base class for ORM models
        Base = declarative_base()

        def get_session():
            """Get a new database session"""
            return Session()

        @contextmanager
        def session_scope():
            """Provide a transactional scope for session operations"""
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

except ImportError:
    # SQLAlchemy not installed, skip ORM setup
    pass


if __name__ == '__main__':
    # Test connection
    print("Testing database connection...")
    try:
        config = get_db_config()
        print(f"Connecting to: {config['host']}:{config['port']}/{config['database']}")
        print(f"SSL mode: {config['sslmode']}")

        if test_connection():
            print("✅ Database connection successful!")

            # Show some database info
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                print(f"PostgreSQL version: {version}")

                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                if tables:
                    print(f"\nExisting tables:")
                    for table in tables:
                        print(f"  - {table[0]}")
                else:
                    print("\nNo tables found. Run schema.sql to create tables.")

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        exit(1)
