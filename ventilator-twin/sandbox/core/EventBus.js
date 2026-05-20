/**
 * Event Bus - Pub/Sub system for sandbox communication
 */

class EventBus {
    constructor() {
        this.events = {};
        this.eventHistory = [];
        this.maxHistorySize = 500;
    }

    /**
     * Subscribe to an event
     * @param {string} eventType - Type of event to listen for
     * @param {function} handler - Callback function
     * @returns {function} Unsubscribe function
     */
    subscribe(eventType, handler) {
        if (!this.events[eventType]) {
            this.events[eventType] = [];
        }

        this.events[eventType].push(handler);

        // Return unsubscribe function
        return () => this.unsubscribe(eventType, handler);
    }

    /**
     * Unsubscribe from an event
     */
    unsubscribe(eventType, handler) {
        if (this.events[eventType]) {
            this.events[eventType] = this.events[eventType].filter(h => h !== handler);
        }
    }

    /**
     * Publish an event
     * @param {string} eventType - Type of event
     * @param {*} data - Event data
     */
    publish(eventType, data = null) {
        // Record in history
        this.eventHistory.push({
            type: eventType,
            data: data,
            timestamp: Date.now()
        });

        if (this.eventHistory.length > this.maxHistorySize) {
            this.eventHistory.shift();
        }

        // Trigger subscribers
        if (this.events[eventType]) {
            this.events[eventType].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in event handler for ${eventType}:`, error);
                }
            });
        }
    }

    /**
     * One-time subscription
     */
    once(eventType, handler) {
        const wrappedHandler = (data) => {
            handler(data);
            this.unsubscribe(eventType, wrappedHandler);
        };

        return this.subscribe(eventType, wrappedHandler);
    }

    /**
     * Get event history
     */
    getHistory(eventType = null, limit = 100) {
        let history = this.eventHistory;

        if (eventType) {
            history = history.filter(e => e.type === eventType);
        }

        return history.slice(-limit);
    }

    /**
     * Clear history
     */
    clearHistory() {
        this.eventHistory = [];
    }

    /**
     * Get subscriber count
     */
    getSubscriberCount(eventType) {
        return this.events[eventType] ? this.events[eventType].length : 0;
    }

    /**
     * Debug: List all event types
     */
    getEventTypes() {
        return Object.keys(this.events);
    }
}

// Standard event types for ventilator twin
const VentilatorEvents = {
    // Parameter changes
    PEEP_CHANGED: 'ventilator:peep_changed',
    FIO2_CHANGED: 'ventilator:fio2_changed',
    TIDAL_VOL_CHANGED: 'ventilator:tidal_vol_changed',
    RESP_RATE_CHANGED: 'ventilator:resp_rate_changed',

    // Simulation control
    SIMULATION_STARTED: 'simulation:started',
    SIMULATION_PAUSED: 'simulation:paused',
    SIMULATION_RESET: 'simulation:reset',
    SIMULATION_SPEED_CHANGED: 'simulation:speed_changed',

    // Sandbox control
    SANDBOX_ENABLED: 'sandbox:enabled',
    SANDBOX_DISABLED: 'sandbox:disabled',
    SANDBOX_RESET: 'sandbox:reset',

    // Alerts
    ALERT_CRITICAL: 'alert:critical',
    ALERT_WARNING: 'alert:warning',
    ALERT_INFO: 'alert:info',

    // Data sync
    STATE_SYNCED: 'state:synced',
    PARAMETERS_VALIDATED: 'parameters:validated',

    // UI events
    VIEW_CHANGED: 'ui:view_changed',
    THEME_TOGGLED: 'ui:theme_toggled',
    PANEL_OPENED: 'ui:panel_opened',
    PANEL_CLOSED: 'ui:panel_closed'
};

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EventBus, VentilatorEvents };
}
