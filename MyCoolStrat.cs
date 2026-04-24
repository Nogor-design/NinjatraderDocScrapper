#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MyCoolStrat : Strategy
    {
        private EMA emaFast;
        private EMA emaSlow;

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "FastLength", GroupName = "Parameters", Order = 0)]
        public int FastLength { get; set; }

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "SlowLength", GroupName = "Parameters", Order = 1)]
        public int SlowLength { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "StopLossTicks", GroupName = "Parameters", Order = 2)]
        public int StopLossTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "ProfitTargetTicks", GroupName = "Parameters", Order = 3)]
        public int ProfitTargetTicks { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "EMA crossover strategy with stop loss and profit target.";
                Name = "MyCoolStrat";
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
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = false;

                FastLength = 10;
                SlowLength = 20;
                StopLossTicks = 20;
                ProfitTargetTicks = 40;
            }
            else if (State == State.Configure)
            {
                SetStopLoss(CalculationMode.Ticks, StopLossTicks);
                SetProfitTarget(CalculationMode.Ticks, ProfitTargetTicks);
            }
            else if (State == State.DataLoaded)
            {
                emaFast = EMA(FastLength);
                emaSlow = EMA(SlowLength);
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0)
                return;

            if (CurrentBar < Math.Max(FastLength, SlowLength))
                return;

            if (CrossAbove(emaFast, emaSlow, 1))
            {
                if (Position.MarketPosition == MarketPosition.Short)
                    ExitShort("ExitShort", "ShortEntry");

                if (Position.MarketPosition != MarketPosition.Long)
                    EnterLong("LongEntry");
            }
            else if (CrossBelow(emaFast, emaSlow, 1))
            {
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong("ExitLong", "LongEntry");

                if (Position.MarketPosition != MarketPosition.Short)
                    EnterShort("ShortEntry");
            }
        }
    }
}
