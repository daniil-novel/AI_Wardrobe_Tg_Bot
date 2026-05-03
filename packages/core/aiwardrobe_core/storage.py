from typing import cast
from uuid import UUID, uuid4

import aioboto3

from aiwardrobe_core.config import Settings, get_settings


def build_storage_key(user_id: UUID, asset_kind: str, filename: str) -> str:
    clean_filename = filename.replace("\\", "/").split("/")[-1]
    return f"users/{user_id}/{asset_kind}/{uuid4()}-{clean_filename}"


class ObjectStorage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def create_presigned_put_url(self, storage_key: str, content_type: str) -> str:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        ) as client:
            signed_url = await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.settings.s3_bucket,
                    "Key": storage_key,
                    "ContentType": content_type,
                },
                ExpiresIn=self.settings.signed_url_ttl_seconds,
            )
            return cast(str, signed_url)

    async def create_presigned_get_url(self, storage_key: str) -> str:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        ) as client:
            signed_url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.settings.s3_bucket, "Key": storage_key},
                ExpiresIn=self.settings.signed_url_ttl_seconds,
            )
            return cast(str, signed_url)
