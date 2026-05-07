import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, encrypt
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.feature_llm_config import FeatureLLMConfig
from app.models.holding import Holding
from app.models.llm_conversation import LLMConversation
from app.models.provider_config import ProviderConfig
from app.models.transaction import Transaction
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.schemas.system_backup import (
    BackupAIAnalysis,
    BackupCashBalance,
    BackupConversation,
    BackupFeatureLLMConfig,
    BackupHolding,
    BackupPortfolio,
    BackupProviderConfig,
    BackupSettings,
    BackupTransaction,
    BackupWatchlistItem,
    SystemBackup,
)

logger = get_logger(__name__)

SUPPORTED_VERSIONS = {"1"}


async def export_backup(db: AsyncSession, user: User) -> SystemBackup:
    user_id = user.id

    # Settings
    settings = BackupSettings(
        currency_primary=user.currency_primary,
        currency_secondary=user.currency_secondary,
        birth_date=user.birth_date,
        plan_to_age=user.plan_to_age,
        privacy_mode=user.privacy_mode,
        telegram_chat_id=user.telegram_chat_id,
        telegram_bot_token=(
            decrypt(user.telegram_bot_token) if user.telegram_bot_token else None
        ),
        sec_api_key=(
            decrypt(user.sec_api_key) if user.sec_api_key else None
        ),
    )

    # Holdings
    holdings_rows = await db.execute(
        select(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    holdings = [
        BackupHolding(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            quantity=holding.quantity,
            avg_cost_price=holding.avg_cost_price,
            currency=holding.currency,
            platform=holding.platform,
            purchased_at=holding.purchased_at,
        )
        for holding, asset in holdings_rows.all()
    ]

    # Transactions
    tx_rows = await db.execute(
        select(Transaction, Asset)
        .join(Asset, Asset.id == Transaction.asset_id)
        .where(Transaction.user_id == user_id)
    )
    transactions = [
        BackupTransaction(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            type=tx.type,
            quantity=tx.quantity,
            price=tx.price,
            fee=tx.fee,
            source=tx.source,
            executed_at=tx.executed_at,
            platform=tx.platform,
        )
        for tx, asset in tx_rows.all()
    ]

    # Provider configs
    pc_rows = await db.execute(
        select(ProviderConfig).where(ProviderConfig.user_id == user_id)
    )
    provider_configs = [
        BackupProviderConfig(
            provider=pc.provider,
            api_key=decrypt(pc.encrypted_api_key) if pc.encrypted_api_key else None,
            host_url=pc.host_url,
            is_connected=pc.is_connected,
        )
        for pc in pc_rows.scalars().all()
    ]

    # Feature LLM configs — resolve provider name via join
    flc_rows = await db.execute(
        select(FeatureLLMConfig, ProviderConfig)
        .join(ProviderConfig, ProviderConfig.id == FeatureLLMConfig.provider_config_id)
        .where(FeatureLLMConfig.user_id == user_id)
    )
    feature_llm_configs = [
        BackupFeatureLLMConfig(
            feature_key=flc.feature_key,
            provider=pc.provider,
            model=flc.model,
            system_prompt=flc.system_prompt,
            is_prompt_customized=flc.is_prompt_customized,
        )
        for flc, pc in flc_rows.all()
    ]

    # Watchlist
    wl_rows = await db.execute(
        select(WatchlistItem, Asset)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == user_id)
    )
    watchlist = [
        BackupWatchlistItem(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            target_price=item.target_price,
            currency=item.currency,
            notes=item.notes,
            alert_enabled=item.alert_enabled,
            created_at=item.created_at,
        )
        for item, asset in wl_rows.all()
    ]

    # Cash balances
    cb_rows = await db.execute(
        select(CashBalance, Asset)
        .join(Asset, Asset.id == CashBalance.asset_id)
        .where(CashBalance.user_id == user_id)
    )
    cash_balances = [
        BackupCashBalance(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            balance=cb.balance,
            snapshot_date=cb.snapshot_date,
            notes=cb.notes,
        )
        for cb, asset in cb_rows.all()
    ]

    # AI analyses + conversations
    analysis_rows = await db.execute(
        select(AIAnalysis, Asset)
        .join(Asset, Asset.id == AIAnalysis.asset_id)
        .where(Asset.user_id == user_id)
    )
    analysis_list = analysis_rows.all()

    if analysis_list:
        analysis_ids = [a.id for a, _ in analysis_list]
        all_convs = await db.execute(
            select(LLMConversation)
            .where(LLMConversation.analysis_id.in_(analysis_ids))
            .order_by(LLMConversation.analysis_id, LLMConversation.message_order)
        )
        convs_by_id: dict = defaultdict(list)
        for c in all_convs.scalars().all():
            convs_by_id[c.analysis_id].append(c)
    else:
        convs_by_id: dict = defaultdict(list)

    ai_analyses = [
        BackupAIAnalysis(
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            verdict=analysis.verdict,
            target_price=analysis.target_price,
            reasoning=analysis.reasoning,
            provider=analysis.provider,
            model=analysis.model,
            created_at=analysis.created_at,
            conversations=[
                BackupConversation(role=c.role, content=c.content, message_order=c.message_order)
                for c in convs_by_id[analysis.id]
            ],
        )
        for analysis, asset in analysis_list
    ]

    logger.info("Exported backup for user=%s", user_id)
    return SystemBackup(
        version="1",
        exported_at=datetime.now(timezone.utc),
        settings=settings,
        portfolio=BackupPortfolio(holdings=holdings, transactions=transactions),
        provider_configs=provider_configs,
        feature_llm_configs=feature_llm_configs,
        watchlist=watchlist,
        cash_balances=cash_balances,
        ai_analyses=ai_analyses,
    )


async def _get_or_create_asset(
    db: AsyncSession, user_id: uuid.UUID, symbol: str, asset_type: str
) -> Asset:
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(),
            user_id=user_id,
            symbol=symbol,
            asset_type=asset_type,
            name=symbol,
            currency="USD",
            metadata_={},
        )
        db.add(asset)
        await db.flush()
    return asset


async def import_backup(db: AsyncSession, user: User, backup: SystemBackup) -> None:
    if backup.version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported backup version: {backup.version}")

    user_id = user.id

    # --- Wipe (dependency order: most dependent first) ---
    analysis_ids_result = await db.execute(
        select(AIAnalysis.id)
        .join(Asset, Asset.id == AIAnalysis.asset_id)
        .where(Asset.user_id == user_id)
    )
    analysis_ids = [row[0] for row in analysis_ids_result.all()]
    if analysis_ids:
        await db.execute(
            delete(LLMConversation).where(LLMConversation.analysis_id.in_(analysis_ids))
        )
        await db.execute(
            delete(AIAnalysis).where(AIAnalysis.id.in_(analysis_ids))
        )

    await db.execute(delete(FeatureLLMConfig).where(FeatureLLMConfig.user_id == user_id))
    await db.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id))
    await db.execute(delete(CashBalance).where(CashBalance.user_id == user_id))
    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await db.execute(delete(Holding).where(Holding.user_id == user_id))
    await db.execute(delete(Asset).where(Asset.user_id == user_id))
    await db.execute(delete(ProviderConfig).where(ProviderConfig.user_id == user_id))
    await db.flush()

    # --- Restore ---
    s = backup.settings
    user.currency_primary = s.currency_primary
    user.currency_secondary = s.currency_secondary
    user.birth_date = s.birth_date
    user.plan_to_age = s.plan_to_age
    user.privacy_mode = s.privacy_mode
    user.telegram_chat_id = s.telegram_chat_id
    user.telegram_bot_token = encrypt(s.telegram_bot_token) if s.telegram_bot_token else None
    user.sec_api_key = encrypt(s.sec_api_key) if s.sec_api_key else None

    # Provider configs — build name→id map for feature config linking
    provider_name_to_id: dict[str, uuid.UUID] = {}
    for pc in backup.provider_configs:
        new_id = uuid.uuid4()
        db.add(ProviderConfig(
            id=new_id,
            user_id=user_id,
            provider=pc.provider,
            encrypted_api_key=encrypt(pc.api_key) if pc.api_key else None,
            host_url=pc.host_url,
            is_connected=pc.is_connected,
            models_cache=[],
        ))
        provider_name_to_id[pc.provider] = new_id
    # flush required: FeatureLLMConfig FK references these IDs
    await db.flush()

    # Holdings
    for h in backup.portfolio.holdings:
        asset = await _get_or_create_asset(db, user_id, h.symbol, h.asset_type)
        db.add(Holding(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            quantity=h.quantity,
            avg_cost_price=h.avg_cost_price,
            currency=h.currency,
            purchased_at=h.purchased_at,
            platform=h.platform,
            updated_at=datetime.now(timezone.utc),
        ))

    # Transactions
    for t in backup.portfolio.transactions:
        asset = await _get_or_create_asset(db, user_id, t.symbol, t.asset_type)
        db.add(Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            type=t.type,
            quantity=t.quantity,
            price=t.price,
            fee=t.fee,
            source=t.source,
            executed_at=t.executed_at,
            platform=t.platform,
        ))

    # Watchlist
    for w in backup.watchlist:
        asset = await _get_or_create_asset(db, user_id, w.symbol, w.asset_type)
        db.add(WatchlistItem(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            target_price=w.target_price,
            currency=w.currency,
            notes=w.notes,
            alert_enabled=w.alert_enabled,
            created_at=w.created_at,
        ))

    # Cash balances
    for cb in backup.cash_balances:
        asset = await _get_or_create_asset(db, user_id, cb.symbol, cb.asset_type)
        db.add(CashBalance(
            id=uuid.uuid4(),
            user_id=user_id,
            asset_id=asset.id,
            balance=cb.balance,
            snapshot_date=cb.snapshot_date,
            notes=cb.notes,
        ))

    # Feature LLM configs
    for flc in backup.feature_llm_configs:
        pc_id = provider_name_to_id.get(flc.provider)
        if pc_id is None:
            logger.warning(
                "Skipping feature config %s — provider %s not in backup",
                flc.feature_key, flc.provider,
            )
            continue
        db.add(FeatureLLMConfig(
            id=uuid.uuid4(),
            user_id=user_id,
            feature_key=flc.feature_key,
            provider_config_id=pc_id,
            model=flc.model,
            system_prompt=flc.system_prompt,
            is_prompt_customized=flc.is_prompt_customized,
        ))

    # AI analyses + conversations
    for analysis in backup.ai_analyses:
        asset = await _get_or_create_asset(db, user_id, analysis.symbol, analysis.asset_type)
        analysis_id = uuid.uuid4()
        db.add(AIAnalysis(
            id=analysis_id,
            asset_id=asset.id,
            verdict=analysis.verdict,
            target_price=analysis.target_price,
            reasoning=analysis.reasoning,
            provider=analysis.provider,
            model=analysis.model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0,
            created_at=analysis.created_at,
        ))
        for conv in analysis.conversations:
            db.add(LLMConversation(
                id=uuid.uuid4(),
                analysis_id=analysis_id,
                role=conv.role,
                content=conv.content,
                message_order=conv.message_order,
            ))

    await db.commit()
    await db.refresh(user)
    logger.info("Import completed for user=%s", user_id)
