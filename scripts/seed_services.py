from app.database.mongodb import connect, close
from app.database.seed import seed_services
if __name__ == "__main__":
    db=connect()
    seed_services(db)
    print("Seeded or updated the 21 provided service records and document checklists.")
    close()
