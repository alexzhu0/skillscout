"""Descriptor-anchored local filesystem primitives with mandatory durability."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable, Final


_REQUIRED_OPEN_FLAGS: Final[tuple[str, ...]] = (
    "O_DIRECTORY",
    "O_NOFOLLOW",
    "O_CLOEXEC",
)
_MISSING: Final[object] = object()


class DurableWriteError(OSError):
    """A required local durability operation failed."""

    def __init__(self, operation: str, *, renamed: bool = False) -> None:
        super().__init__(operation)
        self.operation = operation
        self.renamed = renamed


def _directory_flags() -> int:
    try:
        return (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
    except AttributeError as error:
        raise DurableWriteError("secure_open_unavailable") from error


def _file_flags(base: int) -> int:
    try:
        return base | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as error:
        raise DurableWriteError("secure_open_unavailable") from error


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return (metadata.st_dev, metadata.st_ino)


def _stable_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


class AnchoredDirectory:
    """A verified directory retained by descriptor for one operation lifetime."""

    def __init__(
        self,
        path: Path,
        descriptor: int,
        *,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        self.path = path
        self._descriptor = descriptor
        self._filesystem_seam = filesystem_seam

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        create: bool = False,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> AnchoredDirectory:
        """Open every path component without following a symlink."""

        if any(not hasattr(os, flag) for flag in _REQUIRED_OPEN_FLAGS):
            raise DurableWriteError("secure_open_unavailable")
        required_dir_fd = (os.open, os.mkdir, os.stat, os.unlink, os.rmdir, os.rename)
        if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
            raise DurableWriteError("dir_fd_unavailable")

        absolute = Path(os.path.abspath(os.fspath(path)))
        parts = absolute.parts[1:]
        descriptor = os.open(os.path.sep, _directory_flags())
        current_path = Path(os.path.sep)
        try:
            for index, name in enumerate(parts):
                cls.validate_child_name(name)
                created = False
                try:
                    before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                except FileNotFoundError:
                    if not create:
                        raise DurableWriteError("directory_missing") from None
                    try:
                        os.mkdir(name, 0o700, dir_fd=descriptor)
                    except OSError as error:
                        raise DurableWriteError("mkdir") from error
                    before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    created = True
                if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
                    raise DurableWriteError("directory_invalid")
                try:
                    child = os.open(name, _directory_flags(), dir_fd=descriptor)
                except OSError as error:
                    raise DurableWriteError("directory_open") from error
                opened = os.fstat(child)
                if _identity(before) != _identity(opened) or not stat.S_ISDIR(opened.st_mode):
                    os.close(child)
                    raise DurableWriteError("directory_identity")
                if created:
                    try:
                        if filesystem_seam is not None:
                            filesystem_seam("before_ancestor_directory_fsync")
                        os.fsync(child)
                        os.fsync(descriptor)
                    except OSError as error:
                        os.close(child)
                        raise DurableWriteError("ancestor_directory_fsync") from error
                os.close(descriptor)
                descriptor = child
                current_path /= name
                if index == len(parts) - 1:
                    cls._require_private_owner(opened)
            if not parts:
                cls._require_private_owner(os.fstat(descriptor), allow_system_root=True)
            return cls(
                current_path,
                descriptor,
                filesystem_seam=filesystem_seam,
            )
        except Exception:
            os.close(descriptor)
            raise

    @staticmethod
    def _require_private_owner(
        metadata: os.stat_result, *, allow_system_root: bool = False
    ) -> None:
        if allow_system_root:
            return
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise DurableWriteError("directory_permissions")

    @staticmethod
    def validate_child_name(name: str) -> str:
        if (
            type(name) is not str
            or not name
            or name in {".", ".."}
            or os.path.isabs(name)
            or os.sep in name
            or (os.altsep is not None and os.altsep in name)
        ):
            raise DurableWriteError("child_name_invalid")
        return name

    @property
    def descriptor(self) -> int:
        if self._descriptor < 0:
            raise DurableWriteError("directory_closed")
        return self._descriptor

    def _trip(self, seam: str) -> None:
        if self._filesystem_seam is not None:
            self._filesystem_seam(seam)

    def open_child_directory(
        self, name: str, *, create: bool = False
    ) -> AnchoredDirectory:
        name = self.validate_child_name(name)
        created = False
        try:
            before = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            if not create:
                raise DurableWriteError("directory_missing") from None
            try:
                os.mkdir(name, 0o700, dir_fd=self.descriptor)
                before = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
                created = True
            except OSError as error:
                raise DurableWriteError("mkdir") from error
        if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
            raise DurableWriteError("directory_invalid")
        try:
            child = os.open(name, _directory_flags(), dir_fd=self.descriptor)
            opened = os.fstat(child)
        except OSError as error:
            raise DurableWriteError("directory_open") from error
        if _identity(before) != _identity(opened) or not stat.S_ISDIR(opened.st_mode):
            os.close(child)
            raise DurableWriteError("directory_identity")
        try:
            self._require_private_owner(opened)
            if created:
                self._trip("before_ancestor_directory_fsync")
                os.fsync(child)
                os.fsync(self.descriptor)
        except Exception:
            os.close(child)
            raise
        return AnchoredDirectory(
            self.path / name,
            child,
            filesystem_seam=self._filesystem_seam,
        )

    def stat_child(self, name: str) -> os.stat_result | None:
        name = self.validate_child_name(name)
        try:
            return os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise DurableWriteError("child_stat") from error

    def read_bytes(
        self, name: str, *, max_bytes: int, missing_ok: bool = False
    ) -> bytes | None:
        name = self.validate_child_name(name)
        before = self.stat_child(name)
        if before is None:
            if missing_ok:
                return None
            raise DurableWriteError("file_missing")
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_size > max_bytes
        ):
            raise DurableWriteError("file_invalid")
        descriptor = -1
        try:
            descriptor = os.open(name, _file_flags(os.O_RDONLY), dir_fd=self.descriptor)
            opened = os.fstat(descriptor)
            if _identity(before) != _identity(opened) or not stat.S_ISREG(opened.st_mode):
                raise DurableWriteError("file_identity")
            chunks: list[bytes] = []
            consumed = 0
            while True:
                remaining = max_bytes + 1 - consumed
                chunk = os.read(descriptor, min(8192, remaining))
                if not chunk:
                    break
                consumed += len(chunk)
                if consumed > max_bytes:
                    raise DurableWriteError("file_too_large")
                chunks.append(chunk)
            if _stable_identity(opened) != _stable_identity(os.fstat(descriptor)):
                raise DurableWriteError("file_changed")
            return b"".join(chunks)
        except DurableWriteError:
            raise
        except OSError as error:
            raise DurableWriteError("file_read") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def atomic_write(
        self,
        name: str,
        payload: bytes,
        *,
        max_bytes: int,
        restore_bytes: bytes | object = _MISSING,
        seam_prefix: str = "",
    ) -> None:
        """Write, fsync, rename and fsync the directory, restoring on failure."""

        name = self.validate_child_name(name)
        if type(payload) is not bytes or len(payload) > max_bytes:
            raise DurableWriteError("payload_invalid")
        backup_name = f".{name}.backup"
        had_backup = restore_bytes is not _MISSING
        if had_backup:
            assert isinstance(restore_bytes, bytes)
            self._atomic_write_once(
                backup_name,
                restore_bytes,
                max_bytes=max_bytes,
                seam_prefix=f"{seam_prefix}backup_",
            )
        try:
            self._atomic_write_once(
                name,
                payload,
                max_bytes=max_bytes,
                seam_prefix=seam_prefix,
            )
        except DurableWriteError as failure:
            if failure.renamed:
                self._restore_after_failed_replace(
                    name,
                    backup_name=backup_name if had_backup else None,
                )
            elif had_backup:
                self._best_effort_unlink(backup_name, sync=True)
            raise
        if had_backup:
            self._retire_backup_after_commit(backup_name)

    def _retire_backup_after_commit(self, backup_name: str) -> None:
        """Best-effort housekeeping after the replacement is authoritative."""

        backup_name = self.validate_child_name(backup_name)
        try:
            os.unlink(backup_name, dir_fd=self.descriptor)
            self._trip("after_backup_unlink")
            self._trip("before_backup_cleanup_directory_fsync")
            os.fsync(self.descriptor)
        except (DurableWriteError, OSError):
            pass

    def _atomic_write_once(
        self,
        name: str,
        payload: bytes,
        *,
        max_bytes: int,
        seam_prefix: str,
    ) -> None:
        if len(payload) > max_bytes:
            raise DurableWriteError("payload_invalid")
        existing = self.stat_child(name)
        if existing is not None and (
            not stat.S_ISREG(existing.st_mode) or stat.S_ISLNK(existing.st_mode)
        ):
            raise DurableWriteError("target_invalid")
        temporary = self.validate_child_name(f".{name}.tmp")
        if self.stat_child(temporary) is not None:
            raise DurableWriteError("temporary_exists")
        descriptor = -1
        renamed = False
        try:
            descriptor = os.open(
                temporary,
                _file_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL),
                0o600,
                dir_fd=self.descriptor,
            )
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise DurableWriteError("file_write")
                view = view[written:]
            self._trip(f"before_{seam_prefix}file_fsync")
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            self._trip(f"before_{seam_prefix}rename")
            os.rename(
                temporary,
                name,
                src_dir_fd=self.descriptor,
                dst_dir_fd=self.descriptor,
            )
            renamed = True
            self._trip(f"before_{seam_prefix}directory_fsync")
            os.fsync(self.descriptor)
        except DurableWriteError:
            raise
        except OSError as error:
            raise DurableWriteError("atomic_write", renamed=renamed) from error
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if not renamed:
                self._best_effort_unlink(temporary, sync=False)

    def _restore_after_failed_replace(
        self, name: str, *, backup_name: str | None
    ) -> None:
        try:
            if backup_name is None:
                os.unlink(name, dir_fd=self.descriptor)
            else:
                os.rename(
                    backup_name,
                    name,
                    src_dir_fd=self.descriptor,
                    dst_dir_fd=self.descriptor,
                )
            os.fsync(self.descriptor)
        except OSError:
            pass

    def unlink(self, name: str, *, missing_ok: bool, sync: bool) -> None:
        name = self.validate_child_name(name)
        try:
            os.unlink(name, dir_fd=self.descriptor)
            if sync:
                os.fsync(self.descriptor)
        except FileNotFoundError:
            if not missing_ok:
                raise DurableWriteError("unlink_missing") from None
        except OSError as error:
            raise DurableWriteError("unlink") from error

    def _best_effort_unlink(self, name: str, *, sync: bool) -> None:
        try:
            self.unlink(name, missing_ok=True, sync=sync)
        except DurableWriteError:
            pass

    def remove_child_directory(self, name: str, *, missing_ok: bool = False) -> None:
        name = self.validate_child_name(name)
        try:
            os.rmdir(name, dir_fd=self.descriptor)
            os.fsync(self.descriptor)
        except FileNotFoundError:
            if not missing_ok:
                raise DurableWriteError("rmdir_missing") from None
        except OSError as error:
            raise DurableWriteError("rmdir") from error

    def close(self) -> None:
        if self._descriptor >= 0:
            try:
                os.close(self._descriptor)
            finally:
                self._descriptor = -1

    def __enter__(self) -> AnchoredDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
