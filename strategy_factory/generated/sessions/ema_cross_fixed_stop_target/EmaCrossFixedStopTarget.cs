#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class EmaCrossFixedStopTarget : Strategy
    {
        private EMA fastMa;
        private EMA slowMa;
        private bool riskLocked;
        private int priorTradesCount;
        private double priorTradesCumProfit;
        private int tradesToday;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "A short fast EMA crossing a slower EMA can capture directional momentum during the morning session.";
                Name = "EmaCrossFixedStopTarget";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 50;
                IsInstantiatedOnEachOptimizationIteration = true;

                FastPeriod = 9;
                SlowPeriod = 21;
                StopTicks = 20;
                TargetTicks = 40;
                Quantity = 1;
                MaxTradesPerDay = 3;
                UseSoftPnlLock = true;
                SoftProfitStop = 10000.0;
                SoftLossStop = 10000.0;
                UseHardKill = false;
                HardKillProfit = 800.0;
                HardKillLoss = 400.0;
                StartTime = 83000;
                EndTime = 113000;
            }
            else if (State == State.Configure)
            {
                SetStopLoss(CalculationMode.Ticks, StopTicks);
                SetProfitTarget(CalculationMode.Ticks, TargetTicks);
            }
            else if (State == State.DataLoaded)
            {
                fastMa = EMA(FastPeriod);
                slowMa = EMA(SlowPeriod);
            }
            else if (State == State.Realtime)
            {
                ResetRiskSession();
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0)
                return;

            if (CurrentBar < BarsRequiredToTrade)
                return;

            if (Bars.IsFirstBarOfSession)
                ResetRiskSession();

            if (riskLocked)
                return;

            if (EvaluateSoftRiskLock())
                return;

            if (!IsInTradeWindow())
                return;

            if (tradesToday >= MaxTradesPerDay || GetSessionTradeCount() >= MaxTradesPerDay)
                return;

            if (Position.MarketPosition != MarketPosition.Flat)
                return;

            if (CrossAbove(fastMa, slowMa, 1))
            {
                EnterLong(Quantity, "LongEntry");
                tradesToday++;
                PrintLedgerEvent("ENTER_LONG", "entry_ema_9_21", Close[0]);
            }
            else if (CrossBelow(fastMa, slowMa, 1))
            {
                EnterShort(Quantity, "ShortEntry");
                tradesToday++;
                PrintLedgerEvent("ENTER_SHORT", "entry_ema_9_21", Close[0]);
            }
        }

        protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
        {
            if (State == State.Historical || marketDataUpdate.MarketDataType != MarketDataType.Last)
                return;

            EvaluateHardKill(marketDataUpdate.Price);
        }

        private bool IsInTradeWindow()
        {
            int now = ToTime(Time[0]);
            return now >= StartTime && now <= EndTime;
        }

        private void ResetRiskSession()
        {
            riskLocked = false;
            tradesToday = 0;
            priorTradesCount = SystemPerformance.AllTrades.Count;
            priorTradesCumProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
        }

        private int GetSessionTradeCount()
        {
            return SystemPerformance.AllTrades.Count - priorTradesCount;
        }

        private double GetSessionRealizedPnl()
        {
            return SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit - priorTradesCumProfit;
        }

        private bool EvaluateSoftRiskLock()
        {
            if (GetSessionTradeCount() >= MaxTradesPerDay)
            {
                FlattenForRisk("max trades reached", Close[0]);
                return true;
            }

            if (!UseSoftPnlLock)
                return false;

            double sessionPnl = GetSessionRealizedPnl();
            if (SoftProfitStop > 0 && sessionPnl >= SoftProfitStop)
            {
                FlattenForRisk(string.Format("soft profit stop reached: {0:C2}", sessionPnl), Close[0]);
                return true;
            }

            if (SoftLossStop > 0 && sessionPnl <= -SoftLossStop)
            {
                FlattenForRisk(string.Format("soft loss stop reached: {0:C2}", sessionPnl), Close[0]);
                return true;
            }

            return false;
        }

        private bool EvaluateHardKill(double lastPrice)
        {
            if (!UseHardKill || riskLocked)
                return false;

            double unrealizedPnl = Position.MarketPosition == MarketPosition.Flat
                ? 0
                : Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, lastPrice);
            double currentPnl = GetSessionRealizedPnl() + unrealizedPnl;

            if (HardKillProfit > 0 && currentPnl >= HardKillProfit)
            {
                FlattenForRisk(string.Format("hard profit kill reached: {0:C2}", currentPnl), lastPrice);
                return true;
            }

            if (HardKillLoss > 0 && currentPnl <= -HardKillLoss)
            {
                FlattenForRisk(string.Format("hard loss kill reached: {0:C2}", currentPnl), lastPrice);
                return true;
            }

            return false;
        }

        private void FlattenForRisk(string reason, double priceBasis)
        {
            riskLocked = true;
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong("RiskExitLong", "LongEntry");
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort("RiskExitShort", "ShortEntry");

            PrintLedgerEvent("RISK_LOCK", reason, priceBasis);
        }

        private void PrintLedgerEvent(string eventName, string reason, double priceBasis)
        {
            Print(string.Format(
                CultureInfo.InvariantCulture,
                "SF_LEDGER|strategy_id={0}|timestamp={1:o}|event={2}|reason={3}|price_basis={4}|bar_index={5}|stop_ticks={6}|target_ticks={7}|quantity={8}",
                Name,
                Time[0],
                EscapeLedgerValue(eventName),
                EscapeLedgerValue(reason),
                priceBasis,
                CurrentBar,
                StopTicks,
                TargetTicks,
                Quantity));
        }

        private string EscapeLedgerValue(string value)
        {
            return (value ?? string.Empty).Replace("|", "/").Replace("\r", " ").Replace("\n", " ");
        }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Fast Period", Order = 1, GroupName = "Parameters")]
        public int FastPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Slow Period", Order = 2, GroupName = "Parameters")]
        public int SlowPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Stop Ticks", Order = 3, GroupName = "Risk")]
        public int StopTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Target Ticks", Order = 4, GroupName = "Risk")]
        public int TargetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Quantity", Order = 5, GroupName = "Risk")]
        public int Quantity { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Trades Per Day", Order = 6, GroupName = "Risk")]
        public int MaxTradesPerDay { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Soft PnL Lock", Order = 7, GroupName = "Risk")]
        public bool UseSoftPnlLock { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Soft Profit Stop", Order = 8, GroupName = "Risk")]
        public double SoftProfitStop { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Soft Loss Stop", Order = 9, GroupName = "Risk")]
        public double SoftLossStop { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Hard Kill", Order = 10, GroupName = "Risk")]
        public bool UseHardKill { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Hard Kill Profit", Order = 11, GroupName = "Risk")]
        public double HardKillProfit { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Hard Kill Loss", Order = 12, GroupName = "Risk")]
        public double HardKillLoss { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "Start Time", Description = "HHmmss format", Order = 13, GroupName = "Session")]
        public int StartTime { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "End Time", Description = "HHmmss format", Order = 14, GroupName = "Session")]
        public int EndTime { get; set; }
    }
}
