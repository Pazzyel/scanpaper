import sys

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from scanpaper.selftest import run
        sys.exit(run(sys.argv[sys.argv.index("--self-test") + 1]))
    from scanpaper.app import main
    sys.exit(main())
