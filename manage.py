#!/usr/bin/env python3
"""
Kayendar CLI — Command-line user management tool.

Usage:
  python manage.py adduser <username>         # prompts for password
  python manage.py adduser <username> <pass>  # non-interactive
  python manage.py listusers
  python manage.py deluser <username>
"""

import os
import sys


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    command = args[0]

    data_dir = os.environ.get("KAYENDAR_DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)

    from server import auth, storage

    auth.USER_DB_PATH = os.path.join(data_dir, "users.json")
    storage.set_data_dir(data_dir)

    if command == "adduser":
        if len(args) < 2:
            print("Usage: python manage.py adduser <username> [password]")
            sys.exit(1)
        username = args[1]
        if len(args) >= 3:
            password = args[2]
        else:
            import getpass
            password = getpass.getpass(f"Password for {username}: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match.")
                sys.exit(1)
        try:
            ok = auth.create_user(username, password)
            if ok:
                print(f"User '{username}' created successfully.")
            else:
                print(f"User '{username}' already exists.")
                sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif command == "listusers":
        users = auth.list_users()
        if not users:
            print("No users.")
        else:
            for u in users:
                print(f"  {u}")

    elif command == "deluser":
        if len(args) < 2:
            print("Usage: python manage.py deluser <username>")
            sys.exit(1)
        username = args[1]
        try:
            deleted = auth.delete_user(username)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        if not deleted:
            print(f"User '{username}' not found.")
            sys.exit(1)
        storage.delete_user_data(username)
        print(f"User '{username}' deleted.")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
