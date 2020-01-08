import abc
import datetime
import json
import typing
import uuid
from base64 import b64decode, b64encode

from itsdangerous import BadSignature, SignatureExpired, Signer, TimestampSigner
from starlette.datastructures import Secret

from app.auth.tables import Session as SessionStore


class SessionBackend(abc.ABC):
    """Base class for session backends."""

    @abc.abstractmethod
    async def read(
        self, session_id: str
    ) -> typing.Dict[str, typing.Any]:  # pragma: no cover
        """Read session data from the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def write(
        self, data: typing.Dict, session_id: typing.Optional[str] = None
    ) -> str:  # pragma: no cover
        """Write session data to the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def remove(self, session_id: str) -> None:  # pragma: no cover
        """Remove session data from the storage."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def exists(self, session_id: str) -> bool:  # pragma: no cover
        """Test if storage contains session data for a given session_id."""
        raise NotImplementedError()

    async def generate_id(self) -> str:
        """Generate a new session id."""
        return str(uuid.uuid4())


class CookieBackend(SessionBackend):
    """Stores session data in the browser's cookie as a signed string."""

    def __init__(self, secret_key: typing.Union[str, Secret], max_age: int):
        self._signer = TimestampSigner(str(secret_key))
        self._max_age = max_age

    async def read(self, session_id: str) -> typing.Dict:
        """ A session_id is a signed session value. """
        try:
            data = self._signer.unsign(session_id, max_age=self._max_age)
            return json.loads(b64decode(data))
        except (BadSignature, SignatureExpired):
            return {}

    async def write(
        self, data: typing.Dict, session_id: typing.Optional[str] = None
    ) -> str:
        """ The data is a session id in this backend. """
        encoded_data = b64encode(json.dumps(data).encode("utf-8"))
        return self._signer.sign(encoded_data).decode("utf-8")

    async def remove(self, session_id: str) -> None:
        """ Session data stored on client side - no way to remove it. """

    async def exists(self, session_id: str) -> bool:
        return False


class DatabaseBackend(SessionBackend):
    def __init__(self, secret_key: typing.Union[str, Secret], max_age: int):
        self._signer = TimestampSigner(str(secret_key))
        self._id_signer = Signer(str(secret_key))
        self._max_age = max_age

    async def read(self, session_id: str) -> typing.Dict:
        instance = SessionStore.query.get(session_id)
        if instance:
            try:
                data = self._signer.unsign(instance.data, max_age=self._max_age)
                self._exists = True
                return json.loads(b64decode(data))
            except (BadSignature, SignatureExpired) as e:
                pass

        return {}

    async def write(
        self, data: typing.Dict, session_id: typing.Optional[str] = None
    ) -> str:
        if not session_id:
            new_id = await self.generate_id()
            encoded_id = b64encode(new_id.encode("utf-8"))
            session_id = self._id_signer.sign(encoded_id).decode("utf-8")

        encoded_data = b64encode(json.dumps(data).encode("utf-8"))
        signed_data = self._signer.sign(encoded_data).decode("utf-8")

        await self._save(session_id, signed_data)

        return session_id

    async def remove(self, session_id: str) -> None:
        instance = SessionStore.query.get(session_id)
        if instance:
            instance.delete()

    async def _save(self, session_id: str, data: str) -> None:
        instance = SessionStore.query.get(session_id)
        if instance:
            instance.data = data
        else:
            created = self._signer.get_timestamp()
            expires = created + self._max_age
            instance = SessionStore(
                id=session_id,
                created=created,
                max_age=self._max_age,
                expires=expires,
                data=data
            )
        instance.save()

    async def exists(self, session_id: str) -> bool:
        instance = SessionStore.query.get(session_id)
        return instance is not None


class Session:
    def __init__(self, backend: SessionBackend, session_id: str = None) -> None:
        self.session_id = session_id
        self._data: typing.Dict[str, typing.Any] = {}
        self._backend = backend
        self._is_loaded = False
        self._is_modified = False

    @property
    def is_empty(self) -> bool:
        """Check if session has data."""
        return len(self.keys()) == 0

    @property
    def is_modified(self) -> bool:
        """Check if session data has been modified,"""
        return self._is_modified

    @property
    def data(self) -> typing.Dict:
        return self._data

    async def load(self) -> None:
        """Load data from the backend.
        Subsequent calls do not take any effect."""
        if self._is_loaded:
            return

        if self.session_id:
            self._data = await self._backend.read(self.session_id)

        else:
            self._data = {}
        self._is_loaded = True

    async def persist(self) -> str:
        self.session_id = await self._backend.write(self._data, self.session_id)
        return self.session_id

    async def delete(self) -> None:
        if self.session_id:
            self._data = {}
            self._is_modified = True
            await self._backend.remove(self.session_id)

    async def flush(self) -> str:
        self._is_modified = True
        await self.delete()
        return await self.regenerate_id()

    async def regenerate_id(self) -> str:
        self.session_id = await self._backend.generate_id()
        self._is_modified = True
        return self.session_id

    def keys(self) -> typing.KeysView[str]:
        return self._data.keys()

    def values(self) -> typing.ValuesView[typing.Any]:
        return self._data.values()

    def items(self) -> typing.ItemsView[str, typing.Any]:
        return self._data.items()

    def pop(self, key: str, default: typing.Any = None) -> typing.Any:
        self._is_modified = True
        return self._data.pop(key, default)

    def get(self, name: str, default: typing.Any = None) -> typing.Any:
        return self._data.get(name, default)

    def setdefault(self, key: str, default: typing.Any) -> None:
        self._is_modified = True
        self._data.setdefault(key, default)

    def clear(self) -> None:
        self._is_modified = True
        self._data.clear()

    def update(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self._is_modified = True
        self._data.update(*args, **kwargs)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __setitem__(self, key: str, value: typing.Any) -> None:
        self._is_modified = True
        self._data[key] = value

    def __getitem__(self, key: str) -> typing.Any:
        return self._data[key]

    def __delitem__(self, key: str) -> None:
        self._is_modified = True
        del self._data[key]
