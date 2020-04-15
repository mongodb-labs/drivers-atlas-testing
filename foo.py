import signal


def handler(signum, frame):
    print("HANDLED!")
    exit(0)


signal.signal(signal.SIGINT, handler)


while True:
    pass
