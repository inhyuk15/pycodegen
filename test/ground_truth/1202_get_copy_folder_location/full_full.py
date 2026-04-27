def error(message):
    """
    Throw an error with the given message and immediately quit.

    Args:
        message(str): The message to display.
    """
    fail = "\033[91m"
    end = "\033[0m"
    sys.exit(fail + "Error: {}".format(message) + end)

ERROR_UNABLE_TO_FIND_STORAGE = (
    "Unable to find your {provider} =(\n"
    "If this is the first time you use %s, you may want "
    "to use another provider.\n"
    "Take a look at the documentation [1] to know more about "
    "how to configure mackup.\n\n"
    "[1]: %s" % (MACKUP_APP_NAME, DOCUMENTATION_URL)
)
