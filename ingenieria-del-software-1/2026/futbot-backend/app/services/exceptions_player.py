class AppException(Exception):
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# Ticket: BE [BE] Endpoint Crear Jugador de Club
# Validates PACSS attribute range before hitting the DB, so we control the HTTP code.
class AttributeOutOfRange(AppException):
    def __init__(self, attribute: str, value: int):
        self.attribute = attribute
        self.value = value

        super().__init__(
            message=f"Attribute '{attribute}' must be between 20 and 100. Received: {value}",
            code="ATTRIBUTE_OUT_OF_RANGE",
        )


# Validates that the five PACSS attributes sum exactly 300.
class InvalidAttributeSum(AppException):
    def __init__(self, total: int):
        self.total = total
        self.expected = 300

        super().__init__(
            message=f"Attribute sum must be exactly 300. Received: {total}",
            code="INVALID_ATTRIBUTE_SUM",
        )


# Player names must be unique within the same club.
class DuplicatePlayerName(AppException):
    def __init__(self, name: str):
        self.name = name

        super().__init__(
            message=f"This club already has a player named '{name}'.",
            code="DUPLICATE_PLAYER_NAME",
        )
