#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

// This namespace holds all strategies and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Strategies
{
    public class RegressionTradeStrategy : Strategy
    {
        #region Variables
        private Bollinger bb;
        private VolumeOscillator volumeOsc;
        private EaseOfMovement easeOfMovement;
        private TSF tsf;
        private double previousClose;
        private int tradeCount = 0;
        #endregion

        #region Strategy Parameters
        [NinjaScriptProperty]
        [Display(Name = "BB Period", Description = "Bollinger Bands period", Order = 1, GroupName = "Bollinger Bands")]
        public int BBPeriod { get; set; } = 20;

        [NinjaScriptProperty]
        [Display(Name = "BB Multiplier", Description = "Bollinger Bands multiplier", Order = 2, GroupName = "Bollinger Bands")]
        public double BBMultiplier { get; set; } = 2.0;

        [NinjaScriptProperty]
        [Display(Name = "Volume Fast", Description = "Volume oscillator fast period", Order = 3, GroupName = "Volume")]
        public int VolumeFast { get; set; } = 12;

        [NinjaScriptProperty]
        [Display(Name = "Volume Slow", Description = "Volume oscillator slow period", Order = 4, GroupName = "Volume")]
        public int VolumeSlow { get; set; } = 26;

        [NinjaScriptProperty]
        [Display(Name = "EOM Smoothing", Description = "Ease of Movement smoothing period", Order = 5, GroupName = "Ease of Movement")]
        public int EOMSmoothing { get; set; } = 14;

        [NinjaScriptProperty]
        [Display(Name = "EOM Divisor", Description = "Ease of Movement volume divisor", Order = 6, GroupName = "Ease of Movement")]
        public int EOMDivisor { get; set; } = 10000;

        [NinjaScriptProperty]
        [Display(Name = "TSF Period", Description = "Time Series Forecast period", Order = 7, GroupName = "TSF")]
        public int TSFPeriod { get; set; } = 14;

        [NinjaScriptProperty]
        [Display(Name = "Max Trades Per Session", Description = "Maximum number of trades per session", Order = 8, GroupName = "Risk Management")]
        public int MaxTradesPerSession { get; set; } = 5;

        [NinjaScriptProperty]
        [Display(Name = "Risk Per Trade", Description = "Percentage of account risk per trade", Order = 9, GroupName = "Risk Management")]
        public double RiskPerTrade { get; set; } = 1.0;
        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Regression trade strategy using Bollinger Bands, Volume Oscillator, and Ease of Movement";
                Name = "RegressionTradeStrategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                // Set the default number of bars to wait before entering a trade
                BarsRequiredToTrade = 50;
            }
            else if (State == State.Configure)
            {
                // Initialize indicators
                bb = Bollinger(BBMultiplier, BBPeriod);
                volumeOsc = VolumeOscillator(VolumeFast, VolumeSlow);
                easeOfMovement = EaseOfMovement(EOMSmoothing, EOMDivisor);
                tsf = TSF(TSFPeriod, 0); // Fixed: Added second parameter (0 = Close price)
            }
            else if (State == State.DataLoaded)
            {
                // Initialize variables
                previousClose = Close[1];
            }
        }

        protected override void OnBarUpdate()
        {
            // Only trade after the required number of bars
            if (BarsInProgress != 0 || CurrentBars[0] < BarsRequiredToTrade)
                return;

            // Check if we've reached the maximum trades per session
            if (tradeCount >= MaxTradesPerSession)
                return;

            // Check for long entry conditions
            if (IsLongEntry())
            {
                EnterLong();
                tradeCount++;
            }

            // Check for short entry conditions
            if (IsShortEntry())
            {
                EnterShort();
                tradeCount++;
            }

            // Update previous close
            previousClose = Close[0];
        }

        private bool IsLongEntry()
        {
            // Bollinger Bands below lower band
            if (Close[0] < bb.Lower[0])
            {
                // Volume oscillator is positive (short-term volume above long-term)
                if (volumeOsc[0] > 0)
                {
                    // Ease of Movement crosses above zero (price moving upward with light volume)
                    if (easeOfMovement[0] > 0 && easeOfMovement[1] <= 0)
                    {
                        // TSF shows upward trend
                        if (tsf[0] > tsf[1])
                        {
                            return true;
                        }
                    }
                }
            }
            return false;
        }

        private bool IsShortEntry()
        {
            // Bollinger Bands above upper band
            if (Close[0] > bb.Upper[0])
            {
                // Volume oscillator is negative (short-term volume below long-term)
                if (volumeOsc[0] < 0)
                {
                    // Ease of Movement crosses below zero (price moving downward with light volume)
                    if (easeOfMovement[0] < 0 && easeOfMovement[1] >= 0)
                    {
                        // TSF shows downward trend
                        if (tsf[0] < tsf[1])
                        {
                            return true;
                        }
                    }
                }
            }
            return false;
        }

        // Removed the problematic override methods that don't exist in the base class
        // These methods are not required for basic strategy functionality
        /*
        protected override void OnExecutionUpdate(Execution execution, Order order)
        {
            // Optional: Add execution handling if needed
        }

        protected override void OnOrderUpdate(Order order)
        {
            // Optional: Add order update handling if needed
        }

        protected override void OnPositionUpdate(Position position)
        {
            // Optional: Add position update handling if needed
        }

        protected override void OnSessionStart()
        {
            // Reset trade count at the start of each session
            tradeCount = 0;
        }

        protected override void OnSessionEnd()
        {
            // Optional: Add session end handling if needed
        }
        */
    }
}
