from app.models.room import MAX_LEAGUE_CLUBS, MIN_LEAGUE_CLUBS
from app.services.exceptions_player import AppException


class LeagueNotFound(AppException):
    def __init__(self):
        super().__init__(message="La liga no existe.", code="LEAGUE_NOT_FOUND")


# Ticket: [BE] Create League
# Ya existe una liga con ese nombre (sin distinguir mayúsculas).
class DuplicateLeagueName(AppException):
    def __init__(self, name: str):
        self.name = name

        super().__init__(
            message=f"A league named '{name}' already exists. Choose another name.",
            code="DUPLICATE_LEAGUE_NAME",
        )

# El mínimo de clubes es menor al permitido (3).
class MinClubsTooLow(AppException):
    def __init__(self, min_clubs: int):
        self.min_clubs = min_clubs
        self.min = MIN_LEAGUE_CLUBS

        super().__init__(
            message=f"A league must have at least {self.min} clubs.",
            code="MIN_CLUBS_TOO_LOW",
        )

# El máximo de clubes supera el permitido (30).
class MaxClubsTooHigh(AppException):
    def __init__(self, max_clubs: int):
        self.max_clubs = max_clubs
        self.max = MAX_LEAGUE_CLUBS

        super().__init__(
            message=f"A league can have at most {self.max} clubs.",
            code="MAX_CLUBS_TOO_HIGH",
        )

# El máximo de clubes es menor que el mínimo.
class MaxClubsBelowMin(AppException):
    def __init__(self, max_clubs: int, min_clubs: int):
        self.max_clubs = max_clubs
        self.min_clubs = min_clubs

        super().__init__(
            message="The maximum number of clubs cannot be lower than the minimum.",
            code="MAX_CLUBS_BELOW_MIN",
        )

# La contraseña de una liga privada es inválida (falta, es corta o tiene espacios).
class InvalidLeaguePassword(AppException):
    def __init__(self, reason: str):
        self.reason = reason

        super().__init__(
            message=f"Invalid league password: {reason}.",
            code="INVALID_LEAGUE_PASSWORD",
        )

# Una liga pública no puede tener contraseña.
class PasswordNotAllowedOnPublicLeague(AppException):
    def __init__(self):
        super().__init__(
            message="A public league cannot have a password.",
            code="PASSWORD_NOT_ALLOWED_ON_PUBLIC_LEAGUE",
        )


class LeagueNotFound(AppException):
    def __init__(self):
        super().__init__("La liga no existe", "LEAGUE_NOT_FOUND", status_code=404)


class LeagueNotOpen(AppException):
    def __init__(self):
        super().__init__("La liga ya no admite inscripciones", "LEAGUE_NOT_OPEN")


class WrongLeaguePassword(AppException):
    def __init__(self):
        super().__init__("La contraseña de la liga es incorrecta", "WRONG_LEAGUE_PASSWORD")


class AlreadyInLeague(AppException):
    def __init__(self):
        super().__init__("Tu club ya está inscripto en esta liga", "ALREADY_IN_LEAGUE")


class LeagueLimitReached(AppException):
    def __init__(self, limit: int):
        super().__init__(
            f"Ya estás participando en el máximo de {limit} ligas", "LEAGUE_LIMIT_REACHED"
        )


class LeagueFull(AppException):
    def __init__(self):
        super().__init__("La liga no tiene cupos disponibles", "LEAGUE_FULL")
