/**
 * Sandbox State Management
 * Central reactive state store for isolated simulation
 */

class SandboxState {
    constructor() {
        this.state = {
            // Machine Parameters
            machine: {
                speed: 12,
                targetSpeed: 12,
                cycleRate: 0.2,
                operatingMode: "AC"
            },
            // Thread/Ventilator Parameters
            ventilator: {
                peep: 5.0,
                fio2: 40.0,
                tidalVol: 450.0,
                respRate: 12
            },
            // Environment
            environment: {
                temperature: 36.8,
                humidity: 60,
                vibration: 0.1,
                airflow: 0.5
            },
            // Patient
            patient: {
                spo2: 98.0,
                hr: 80,
                map: 75,
                compliance: 1.0
            },
            // Energy
            energy: {
                voltage: 220,
                current: 5,
                powerConsumption: 1100
            },
            // Simulation Control
            simulation: {
                isRunning: false,
                isSandboxMode: true,
                speed: 1.0,
                timestamp: Date.now()
            }
        };

        this.listeners = {};
        this.history = [];
    }

    // Getters
    getState() {
        return { ...this.state };
    }

    getParameter(path) {
        const keys = path.split('.');
        let value = this.state;
        for (const key of keys) {
            value = value[key];
        }
        return value;
    }

    // Setters
    setState(newState) {
        this.state = { ...this.state, ...newState };
        this.notify('stateChanged');
    }

    setParameter(path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        let target = this.state;
        
        for (const key of keys) {
            if (!target[key]) target[key] = {};
            target = target[key];
        }
        
        target[lastKey] = value;
        this.recordHistory();
        this.notify('parameterChanged', { path, value });
    }

    // Batch update
    batchUpdate(updates) {
        for (const [path, value] of Object.entries(updates)) {
            const keys = path.split('.');
            const lastKey = keys.pop();
            let target = this.state;
            
            for (const key of keys) {
                if (!target[key]) target[key] = {};
                target = target[key];
            }
            
            target[lastKey] = value;
        }
        
        this.recordHistory();
        this.notify('batchUpdated', updates);
    }

    // Event System
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    off(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    }

    notify(event, data = null) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in listener for ${event}:`, error);
                }
            });
        }
    }

    // History tracking
    recordHistory() {
        this.history.push({
            timestamp: Date.now(),
            state: JSON.parse(JSON.stringify(this.state))
        });

        // Keep only last 1000 records
        if (this.history.length > 1000) {
            this.history.shift();
        }
    }

    getHistory(limit = 100) {
        return this.history.slice(-limit);
    }

    // Validation
    validateParameters() {
        const errors = [];

        if (this.state.ventilator.peep < 3 || this.state.ventilator.peep > 20) {
            errors.push("PEEP out of range (3-20 cmH₂O)");
        }
        if (this.state.ventilator.fio2 < 21 || this.state.ventilator.fio2 > 100) {
            errors.push("FiO₂ out of range (21-100%)");
        }
        if (this.state.ventilator.tidalVol < 200 || this.state.ventilator.tidalVol > 800) {
            errors.push("Tidal Volume out of range (200-800 mL)");
        }

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    // Reset to defaults
    reset() {
        this.state = {
            machine: { speed: 12, targetSpeed: 12, cycleRate: 0.2, operatingMode: "AC" },
            ventilator: { peep: 5.0, fio2: 40.0, tidalVol: 450.0, respRate: 12 },
            environment: { temperature: 36.8, humidity: 60, vibration: 0.1, airflow: 0.5 },
            patient: { spo2: 98.0, hr: 80, map: 75, compliance: 1.0 },
            energy: { voltage: 220, current: 5, powerConsumption: 1100 },
            simulation: { isRunning: false, isSandboxMode: true, speed: 1.0, timestamp: Date.now() }
        };
        this.notify('reset');
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SandboxState;
}
