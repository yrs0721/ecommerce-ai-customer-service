import platform
import sys


def main():
    print("Environment check")
    print("-----------------")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Operating system: {platform.platform()}")
    print("Project environment is ready.")


if __name__ == "__main__":
    main()