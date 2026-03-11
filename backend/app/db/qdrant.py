import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    QuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

from app.config import settings

logger = structlog.get_logger(__name__)

_qdrant_client: AsyncQdrantClient | None = None


async def init_qdrant() -> None:
    global _qdrant_client
    if settings.dev_mode:
        _qdrant_client = AsyncQdrantClient(":memory:")
        logger.info("qdrant.dev_inmemory")
    else:
        _qdrant_client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )

    await _ensure_collection()
    target = ":memory:" if settings.dev_mode else settings.qdrant_host
    logger.info("qdrant.ready", host=target, collection=settings.qdrant_collection)


async def _ensure_collection() -> None:
    client = get_qdrant()
    exists = await client.collection_exists(settings.qdrant_collection)
    if not exists:
        create_kwargs: dict = dict(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
        )
        if not settings.dev_mode:
            # Quantization not supported by in-memory client
            create_kwargs["quantization_config"] = QuantizationConfig(
                scalar=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                )
            )
            create_kwargs["on_disk_payload"] = True
        await client.create_collection(**create_kwargs)
        # Create payload indexes
        for field, schema in [
            ("doc_id", PayloadSchemaType.KEYWORD),
            ("filename", PayloadSchemaType.KEYWORD),
            ("page_number", PayloadSchemaType.INTEGER),
            ("language", PayloadSchemaType.KEYWORD),
        ]:
            await client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=schema,
            )
        logger.info("qdrant.collection_created", collection=settings.qdrant_collection)
    else:
        logger.info("qdrant.collection_exists", collection=settings.qdrant_collection)


async def close_qdrant() -> None:
    global _qdrant_client
    if _qdrant_client:
        await _qdrant_client.close()
        _qdrant_client = None
    logger.info("qdrant.closed")


def get_qdrant() -> AsyncQdrantClient:
    if _qdrant_client is None:
        raise RuntimeError("Qdrant client not initialized")
    return _qdrant_client
