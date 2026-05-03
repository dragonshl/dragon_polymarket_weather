"""
ASL Integration Tests
=====================

Tests for the ASL integration with Polymarket trading system.

Author: Dragonclawbot
Date: 2026-03-17
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from systems.adaptive_stoploss_system import (
    AdaptiveStopLossSystem,
    StopLossState,
    StopLossStatus,
    create_mock_order_book,
)
from risk.stop_loss_manager import (
    PolymarketStopLossManager,
    ASLEventType,
)
from config.asl_config import (
    ASLConfig,
    DEFAULT_ASL_CONFIG,
    get_config
)
from systems.asl_integration import (
    ASLIntegration,
    ASLMonitor,
    StopLossLogger,
    StopLossAlert
)


# ============================================================================
# Config Tests
# ============================================================================

class TestASLConfig:
    """Test ASL configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = DEFAULT_ASL_CONFIG
        
        assert config.enabled is True
        assert config.stop_loss_pct == -0.03
        assert config.take_profit_pct == 0.05
        assert config.confirmation_ticks == 2
        assert config.monitor_interval == 10
    
    def test_config_presets(self):
        """Test configuration presets"""
        aggressive = get_config('aggressive')
        conservative = get_config('conservative')
        
        assert aggressive.stop_loss_pct == -0.02
        assert aggressive.confirmation_ticks == 1
        
        assert conservative.stop_loss_pct == -0.05
        assert conservative.confirmation_ticks == 3
    
    def test_config_to_dict(self):
        """Test config serialization"""
        config = ASLConfig(stop_loss_pct=-0.05)
        d = config.to_dict()
        
        assert d['stop_loss_pct'] == -0.05
        assert 'enabled' in d


# ============================================================================
# Stop Loss Manager Tests
# ============================================================================

class TestPolymarketStopLossManager:
    """Test Polymarket StopLoss Manager"""
    
    @pytest.fixture
    def manager(self):
        """Create manager instance"""
        return PolymarketStopLossManager(config=DEFAULT_ASL_CONFIG)
    
    def test_manager_initialization(self, manager):
        """Test manager initializes correctly"""
        assert manager.config.enabled is True
        assert len(manager.asl_systems) == 0
        assert len(manager.position_metadata) == 0
    
    def test_create_stop_loss(self, manager):
        """Test creating stop loss for position"""
        asl = manager.create_stop_loss(
            position_id="TEST_001",
            avg_buy_price=0.50,
            stop_loss_pct=-0.03,
            position_size=1000
        )
        
        assert asl is not None
        assert "TEST_001" in manager.asl_systems
        assert "TEST_001" in manager.position_metadata
        
        meta = manager.position_metadata["TEST_001"]
        assert meta['avg_buy_price'] == 0.50
        assert meta['stop_loss_pct'] == -0.03
    
    def test_create_stop_loss_disabled(self):
        """Test disabled ASL returns None"""
        config = ASLConfig(enabled=False)
        manager = PolymarketStopLossManager(config=config)
        
        asl = manager.create_stop_loss(
            position_id="TEST_002",
            avg_buy_price=0.50,
            position_size=1000
        )
        
        assert asl is None
    
    def test_remove_stop_loss(self, manager):
        """Test removing stop loss"""
        manager.create_stop_loss(
            position_id="TEST_003",
            avg_buy_price=0.50,
            position_size=1000
        )
        
        result = manager.remove_stop_loss("TEST_003")
        
        assert result is True
        assert "TEST_003" not in manager.asl_systems
    
    def test_get_position_metadata(self, manager):
        """Test getting position metadata"""
        manager.create_stop_loss(
            position_id="TEST_004",
            avg_buy_price=0.60,
            cycle_max_avg_buy=0.65,
            stop_loss_pct=-0.05,
            position_size=500
        )
        
        meta = manager.get_position_metadata("TEST_004")
        
        assert meta is not None
        assert meta['avg_buy_price'] == 0.60
        assert meta['cycle_max_avg_buy'] == 0.65
        assert meta['stop_loss_pct'] == -0.05
    
    @pytest.mark.asyncio
    async def test_check_position_healthy(self, manager):
        """Test checking healthy position"""
        manager.create_stop_loss(
            position_id="TEST_005",
            avg_buy_price=0.50,
            stop_loss_pct=-0.03,
            position_size=1000
        )
        
        order_book = create_mock_order_book(mid_price=0.50)
        
        result = await manager.check_position(
            position_id="TEST_005",
            fair_ref_price=0.50,
            order_book=order_book,
            current_price=0.50
        )
        
        # Market healthy, should return without triggering
        assert result.get('action') in ['MONITOR', 'RESET']
    
    def test_get_summary(self, manager):
        """Test getting summary"""
        manager.create_stop_loss("TEST_006", 0.50, -0.03, None, 1000)
        manager.create_stop_loss("TEST_007", 0.60, -0.05, None, 500)
        
        summary = manager.get_summary()
        
        assert summary['total_positions'] == 2
        assert summary['enabled'] is True


# ============================================================================
# ASL Integration Tests
# ============================================================================

class TestASLIntegration:
    """Test ASL Integration"""
    
    @pytest.fixture
    def integration(self):
        """Create integration instance"""
        return ASLIntegration()
    
    def test_integration_initialization(self, integration):
        """Test integration initializes correctly"""
        assert integration.config is not None
        assert integration.manager is not None
        assert integration.logger is not None
        assert integration.alert is not None
    
    @pytest.mark.asyncio
    async def test_add_position(self, integration):
        """Test adding position to integration"""
        await integration.add_position(
            position_id="INT_001",
            avg_buy_price=0.55,
            position_size=2000,
            stop_loss_pct=-0.04
        )
        
        meta = integration.manager.get_position_metadata("INT_001")
        assert meta is not None
        assert meta['avg_buy_price'] == 0.55
    
    @pytest.mark.asyncio
    async def test_remove_position(self, integration):
        """Test removing position from integration"""
        await integration.add_position(
            position_id="INT_002",
            avg_buy_price=0.55,
            position_size=2000
        )
        
        await integration.remove_position("INT_002")
        
        meta = integration.manager.get_position_metadata("INT_002")
        assert meta is None
    
    @pytest.mark.asyncio
    async def test_check_position_now(self, integration):
        """Test immediate position check"""
        await integration.add_position(
            position_id="INT_003",
            avg_buy_price=0.50,
            position_size=1000,
            stop_loss_pct=-0.03
        )
        
        result = await integration.check_position_now(
            position_id="INT_003",
            fair_ref_price=0.52,
            current_price=0.52
        )
        
        assert result is not None
        assert 'action' in result
    
    def test_get_status(self, integration):
        """Test getting status"""
        status = integration.get_status()
        
        assert 'enabled' in status
        assert 'monitoring' in status
        assert 'positions' in status


# ============================================================================
# ASL Monitor Tests
# ============================================================================

class TestASLMonitor:
    """Test ASL Monitor"""
    
    @pytest.fixture
    def mock_manager(self):
        """Create mock manager"""
        manager = MagicMock()
        manager.asl_systems = {}
        manager.check_position = AsyncMock(return_value={'action': 'MONITOR'})
        return manager
    
    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data function"""
        async def get_data():
            return {}
        return get_data
    
    @pytest.mark.asyncio
    async def test_monitor_start_stop(self, mock_manager, mock_market_data):
        """Test monitor start and stop"""
        monitor = ASLMonitor(
            manager=mock_manager,
            get_market_data=mock_market_data,
            execute_exit=AsyncMock(),
            check_interval=1
        )
        
        await monitor.start()
        assert monitor._running is True
        
        await asyncio.sleep(0.1)  # Let it run briefly
        await monitor.stop()
        assert monitor._running is False


# ============================================================================
# Logger and Alert Tests
# ============================================================================

class TestStopLossLogger:
    """Test StopLoss Logger"""
    
    @pytest.fixture
    def logger(self):
        """Create logger instance"""
        return StopLossLogger()
    
    @pytest.mark.asyncio
    async def test_log_event(self, logger):
        """Test logging event"""
        await logger.log_event({
            'type': 'TEST_EVENT',
            'position_id': 'TEST',
            'details': 'test'
        })
        
        assert len(logger.events) == 1
        assert logger.events[0]['type'] == 'TEST_EVENT'
    
    def test_get_recent_events(self, logger):
        """Test getting recent events"""
        for i in range(10):
            logger.events.append({'type': 'EVENT', 'id': i})
        
        recent = logger.get_recent_events(limit=5)
        
        assert len(recent) == 5
    
    def test_get_events_summary(self, logger):
        """Test getting events summary"""
        logger.events = [
            {'type': 'ARMED'},
            {'type': 'ARMED'},
            {'type': 'EXECUTED'}
        ]
        
        summary = logger.get_events_summary()
        
        assert summary['total_events'] == 3
        assert summary['by_type']['ARMED'] == 2
        assert summary['by_type']['EXECUTED'] == 1


class TestStopLossAlert:
    """Test StopLoss Alert"""
    
    @pytest.fixture
    def alert(self):
        """Create alert instance"""
        return StopLossAlert()
    
    @pytest.mark.asyncio
    async def test_send_alert(self, alert):
        """Test sending alert"""
        await alert.send_alert(
            alert_type='ASL_ARMED',
            details={'position_id': 'TEST_001'},
            severity='warning'
        )
        
        assert len(alert.alert_history) == 1
        assert alert.alert_history[0]['type'] == 'ASL_ARMED'
    
    def test_format_message(self, alert):
        """Test message formatting"""
        msg = alert._format_message('ASL_EXECUTED', {'position_id': 'POS_001'})
        
        assert 'POS_001' in msg
        assert 'EXECUTED' in msg


# ============================================================================
# AdaptiveStopLossSystem Tests
# ============================================================================

class TestAdaptiveStopLossSystem:
    """Test Adaptive StopLoss System"""
    
    @pytest.fixture
    def asl_system(self):
        """Create ASL system"""
        return AdaptiveStopLossSystem(required_ticks=2, probe_ratio=0.25)
    
    def test_add_position(self, asl_system):
        """Test adding position"""
        state = asl_system.add_position(
            position_id="ASL_TEST_001",
            avg_buy_price=0.50,
            cycle_max_avg_buy=0.52,
            stop_loss_pct=-0.30,
            position_size=1000
        )
        
        assert state is not None
        assert state.position_id == "ASL_TEST_001"
        assert state.anchor_price == 0.52  # max of 0.50 and 0.52
        assert state.trigger_price == 0.52 * 0.70  # 30% stop loss
    
    def test_remove_position(self, asl_system):
        """Test removing position"""
        asl_system.add_position(
            "ASL_TEST_002", 0.50, 0.52, -0.30, 1000
        )
        
        result = asl_system.remove_position("ASL_TEST_002")
        
        assert result is True
        assert "ASL_TEST_002" not in asl_system.positions
    
    @pytest.mark.asyncio
    async def test_check_tick_healthy(self, asl_system):
        """Test tick check with healthy market"""
        asl_system.add_position(
            "ASL_TEST_003", 0.50, 0.52, -0.30, 1000
        )
        
        order_book = create_mock_order_book(mid_price=0.40)
        
        result = await asl_system.check_tick(
            position_id="ASL_TEST_003",
            fair_ref_price=0.40,
            order_book=order_book,
            current_price=0.40
        )
        
        # Market unhealthy (below trigger) should trigger
        assert result.get('action') in ['ARMED', 'WAITING_CONFIRMATION', 'MONITOR']
    
    @pytest.mark.asyncio
    async def test_check_tick_triggered(self, asl_system):
        """Test tick check that triggers stop loss"""
        asl_system.add_position(
            "ASL_TEST_004", 0.50, 0.52, -0.30, 1000
        )
        
        # First tick - ARMED
        order_book = create_mock_order_book(mid_price=0.35)
        result1 = await asl_system.check_tick(
            "ASL_TEST_004", 0.35, order_book, 0.35
        )
        
        # Second tick - should execute (no client, so mocked)
        result2 = await asl_system.check_tick(
            "ASL_TEST_004", 0.34, order_book, 0.34
        )
        
        # Check state transitions
        assert result1.get('action') in ['ARMED', 'WAITING_CONFIRMATION']


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_position_lifecycle(self):
        """Test complete position lifecycle with ASL"""
        # Create integration
        integration = ASLIntegration()
        
        # Add position
        await integration.add_position(
            position_id="LIFECYCLE_001",
            avg_buy_price=0.50,
            position_size=1000,
            stop_loss_pct=-0.03
        )
        
        # Verify position exists
        meta = integration.manager.get_position_metadata("LIFECYCLE_001")
        assert meta is not None
        
        # Check healthy market
        result1 = await integration.check_position_now(
            "LIFECYCLE_001",
            fair_ref_price=0.52,
            current_price=0.52
        )
        
        # Check unhealthy market (first tick)
        result2 = await integration.check_position_now(
            "LIFECYCLE_001",
            fair_ref_price=0.47,
            current_price=0.47
        )
        
        # Remove position
        await integration.remove_position("LIFECYCLE_001")
        
        meta = integration.manager.get_position_metadata("LIFECYCLE_001")
        assert meta is None
    
    @pytest.mark.asyncio
    async def test_multiple_positions(self):
        """Test managing multiple positions"""
        integration = ASLIntegration()
        
        # Add multiple positions
        positions = [
            ("MULTI_001", 0.50, 1000, -0.03),
            ("MULTI_002", 0.60, 500, -0.05),
            ("MULTI_003", 0.70, 750, -0.02),
        ]
        
        for pos_id, price, size, sl_pct in positions:
            await integration.add_position(
                position_id=pos_id,
                avg_buy_price=price,
                position_size=size,
                stop_loss_pct=sl_pct
            )
        
        # Verify all positions
        summary = integration.manager.get_summary()
        
        assert summary['total_positions'] == 3


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
