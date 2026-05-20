/**
 * Parameter Engine - Handles validation, constraints, and propagation
 */

class ParameterEngine {
    constructor(state, eventBus) {
        this.state = state;
        this.eventBus = eventBus;

        // Define parameter constraints
        this.constraints = {
            'ventilator.peep': { min: 3, max: 20, unit: 'cmH₂O', type: 'number' },
            'ventilator.fio2': { min: 21, max: 100, unit: '%', type: 'number' },
            'ventilator.tidalVol': { min: 200, max: 800, unit: 'mL', type: 'number' },
            'ventilator.respRate': { min: 6, max: 40, unit: 'bpm', type: 'integer' },
            'environment.temperature': { min: 15, max: 40, unit: '°C', type: 'number' },
            'environment.humidity': { min: 30, max: 90, unit: '%', type: 'number' },
            'environment.vibration': { min: 0, max: 5, unit: 'm/s²', type: 'number' },
            'machine.speed': { min: 0, max: 100, unit: 'rpm', type: 'number' },
            'energy.voltage': { min: 180, max: 240, unit: 'V', type: 'number' },
            'energy.current': { min: 0, max: 20, unit: 'A', type: 'number' }
        };

        // Define derived/calculated parameters
        this.derived = {
            'energy.powerConsumption': () => {
                return this.state.getParameter('energy.voltage') * 
                       this.state.getParameter('energy.current');
            },
            'ventilator.pressure': () => {
                const peep = this.state.getParameter('ventilator.peep');
                const tidalVol = this.state.getParameter('ventilator.tidalVol');
                // Simplified pressure model
                return 5 + peep * 0.3 + (tidalVol - 350) * 0.01;
            }
        };

        // Safety thresholds for alerts
        this.safetyThresholds = {
            peep_high: 15,
            peep_critical: 20,
            fio2_high: 80,
            fio2_critical: 95,
            tidalVol_high: 600,
            tidalVol_critical: 750,
            spo2_low: 92,
            spo2_critical: 88
        };
    }

    /**
     * Validate a single parameter
     */
    validateParameter(path, value) {
        const constraint = this.constraints[path];

        if (!constraint) {
            return { valid: true, value: value };
        }

        // Type check
        if (constraint.type === 'integer') {
            if (!Number.isInteger(value)) {
                value = Math.round(value);
            }
        } else if (constraint.type === 'number') {
            if (typeof value !== 'number') {
                return { valid: false, error: `Invalid type: expected number, got ${typeof value}` };
            }
        }

        // Range check
        if (value < constraint.min) {
            return { 
                valid: false, 
                error: `Value below minimum (${constraint.min} ${constraint.unit})`,
                value: constraint.min
            };
        }

        if (value > constraint.max) {
            return {
                valid: false,
                error: `Value above maximum (${constraint.max} ${constraint.unit})`,
                value: constraint.max
            };
        }

        return { valid: true, value: value };
    }

    /**
     * Set a parameter with validation
     */
    setParameter(path, value) {
        const validation = this.validateParameter(path, value);

        if (!validation.valid) {
            console.warn(`Parameter validation failed for ${path}:`, validation.error);
            // Clamp to valid range
            value = validation.value;
        }

        // Set the parameter
        this.state.setParameter(path, value);

        // Update derived parameters
        this.updateDerived();

        // Check safety thresholds
        this.checkSafetyThresholds();

        // Emit specific event for this parameter
        const eventType = `ventilator:${path.split('.')[1]}_changed`;
        if (this.eventBus) {
            this.eventBus.publish(eventType, { path, value });
        }

        return { valid: validation.valid, value: value };
    }

    /**
     * Batch set parameters
     */
    batchSetParameters(updates) {
        const results = {};
        const validated = {};

        // Validate all first
        for (const [path, value] of Object.entries(updates)) {
            const validation = this.validateParameter(path, value);
            results[path] = validation;
            validated[path] = validation.value;
        }

        // Apply all at once
        this.state.batchUpdate(validated);
        this.updateDerived();
        this.checkSafetyThresholds();

        return results;
    }

    /**
     * Update derived/calculated parameters
     */
    updateDerived() {
        for (const [path, calculator] of Object.entries(this.derived)) {
            try {
                const value = calculator();
                this.state.setParameter(path, value);
            } catch (error) {
                console.error(`Error calculating ${path}:`, error);
            }
        }
    }

    /**
     * Check safety thresholds and emit alerts
     */
    checkSafetyThresholds() {
        const peep = this.state.getParameter('ventilator.peep');
        const fio2 = this.state.getParameter('ventilator.fio2');
        const tidalVol = this.state.getParameter('ventilator.tidalVol');
        const spo2 = this.state.getParameter('patient.spo2');

        const alerts = [];

        // PEEP checks
        if (peep >= this.safetyThresholds.peep_critical) {
            alerts.push({
                level: 'critical',
                parameter: 'PEEP',
                value: peep,
                threshold: this.safetyThresholds.peep_critical,
                message: `Critical PEEP level: ${peep.toFixed(1)} cmH₂O`
            });
        } else if (peep >= this.safetyThresholds.peep_high) {
            alerts.push({
                level: 'warning',
                parameter: 'PEEP',
                value: peep,
                threshold: this.safetyThresholds.peep_high,
                message: `High PEEP level: ${peep.toFixed(1)} cmH₂O`
            });
        }

        // FiO2 checks
        if (fio2 >= this.safetyThresholds.fio2_critical) {
            alerts.push({
                level: 'critical',
                parameter: 'FiO₂',
                value: fio2,
                threshold: this.safetyThresholds.fio2_critical,
                message: `Critical FiO₂ level: ${fio2.toFixed(0)}%`
            });
        } else if (fio2 >= this.safetyThresholds.fio2_high) {
            alerts.push({
                level: 'warning',
                parameter: 'FiO₂',
                value: fio2,
                threshold: this.safetyThresholds.fio2_high,
                message: `High FiO₂ level: ${fio2.toFixed(0)}%`
            });
        }

        // Tidal Volume checks
        if (tidalVol >= this.safetyThresholds.tidalVol_critical) {
            alerts.push({
                level: 'critical',
                parameter: 'Tidal Volume',
                value: tidalVol,
                threshold: this.safetyThresholds.tidalVol_critical,
                message: `Critical tidal volume: ${tidalVol.toFixed(0)} mL (VILI risk)`
            });
        } else if (tidalVol >= this.safetyThresholds.tidalVol_high) {
            alerts.push({
                level: 'warning',
                parameter: 'Tidal Volume',
                value: tidalVol,
                threshold: this.safetyThresholds.tidalVol_high,
                message: `High tidal volume: ${tidalVol.toFixed(0)} mL`
            });
        }

        // SpO2 checks
        if (spo2 <= this.safetyThresholds.spo2_critical) {
            alerts.push({
                level: 'critical',
                parameter: 'SpO₂',
                value: spo2,
                threshold: this.safetyThresholds.spo2_critical,
                message: `Critical SpO₂: ${spo2.toFixed(1)}% (severe hypoxemia)`
            });
        } else if (spo2 <= this.safetyThresholds.spo2_low) {
            alerts.push({
                level: 'warning',
                parameter: 'SpO₂',
                value: spo2,
                threshold: this.safetyThresholds.spo2_low,
                message: `Low SpO₂: ${spo2.toFixed(1)}%`
            });
        }

        // Emit alerts
        if (this.eventBus) {
            alerts.forEach(alert => {
                const eventType = alert.level === 'critical' ? 
                    'alert:critical' : 'alert:warning';
                this.eventBus.publish(eventType, alert);
            });
        }

        return alerts;
    }

    /**
     * Get parameter info
     */
    getParameterInfo(path) {
        const constraint = this.constraints[path];
        const value = this.state.getParameter(path);

        if (!constraint) {
            return { path, value, constrained: false };
        }

        return {
            path,
            value,
            constrained: true,
            min: constraint.min,
            max: constraint.max,
            unit: constraint.unit,
            type: constraint.type
        };
    }

    /**
     * Get all parameters with info
     */
    getAllParametersInfo() {
        const info = {};

        for (const path of Object.keys(this.constraints)) {
            info[path] = this.getParameterInfo(path);
        }

        return info;
    }

    /**
     * Optimize parameters based on mode
     */
    optimize(mode = 'balanced') {
        const updates = {};

        switch (mode) {
            case 'oxygenation':
                updates['ventilator.fio2'] = 70;
                updates['ventilator.peep'] = 10;
                break;
            case 'ventilation':
                updates['ventilator.tidalVol'] = 500;
                updates['ventilator.respRate'] = 16;
                break;
            case 'safety':
                updates['ventilator.tidalVol'] = 450;
                updates['ventilator.peep'] = 8;
                updates['ventilator.fio2'] = 40;
                break;
            case 'balanced':
            default:
                // Balanced settings
                updates['ventilator.peep'] = 7;
                updates['ventilator.fio2'] = 45;
                updates['ventilator.tidalVol'] = 450;
                break;
        }

        return this.batchSetParameters(updates);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ParameterEngine;
}
