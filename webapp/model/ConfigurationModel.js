sap.ui.define([
    "sap/ui/model/json/JSONModel",
    "../service/ApiService"
], function (JSONModel, ApiService) {
    "use strict";

    return JSONModel.extend("persona.discussion.lab.model.ConfigurationModel", {
        constructor: function () {
            JSONModel.apply(this, [{
                model: "gpt-4.1-mini",
                temperature: 0.3,
                maxRounds: 1,
                tokenLimit: 1200,
                promptTemplates: {
                    global: {}
                },
                implementedStrategies: [],
                strategySpecifications: [],
                strategyOptions: [],
                selectedStrategySpecKey: "",
                selectedStrategySpec: null,
                selectedStrategySpecDeletable: false,
                busy: false,
                error: null
            }]);
        },

        _buildStrategyOptions: function (specifications) {
            return (specifications || []).map(function (spec) {
                const key = spec.strategyKey || "";
                const name = spec.displayName || key;
                return {
                    key: key,
                    text: `${name} (${key})`
                };
            });
        },

        _cloneStrategySpecification: function (specification) {
            if (!specification) {
                return null;
            }

            return Object.assign({}, specification, {
                promptTemplates: Object.assign({}, specification.promptTemplates || {})
            });
        },

        _syncSelectedStrategySpecification: function () {
            const selectedKey = this.getProperty("/selectedStrategySpecKey");
            const selectedSpec = this.getProperty("/selectedStrategySpec");
            if (!selectedKey || !selectedSpec) {
                return;
            }

            const specs = [...(this.getProperty("/strategySpecifications") || [])];
            const index = specs.findIndex(function (item) {
                return item.strategyKey === selectedKey;
            });
            if (index === -1) {
                return;
            }

            specs[index] = this._cloneStrategySpecification(selectedSpec);
            this.setProperty("/strategySpecifications", specs);
            this.setProperty("/strategyOptions", this._buildStrategyOptions(specs));
        },

        _selectStrategySpecByKey: function (strategyKey) {
            this._syncSelectedStrategySpecification();
            const specs = this.getProperty("/strategySpecifications") || [];
            const selected = specs.find(function (item) {
                return item.strategyKey === strategyKey;
            }) || null;
            const implemented = this.getProperty("/implementedStrategies") || [];
            const isImplemented = implemented.some(function (item) {
                return item.key === strategyKey;
            });
            this.setProperty("/selectedStrategySpecKey", strategyKey || "");
            this.setProperty("/selectedStrategySpec", this._cloneStrategySpecification(selected));
            this.setProperty("/selectedStrategySpecDeletable", Boolean(selected && !isImplemented));
        },

        selectStrategySpecification: function (strategyKey) {
            this._selectStrategySpecByKey(strategyKey);
        },

        addStrategySpecification: function () {
            this._syncSelectedStrategySpecification();
            const specs = [...(this.getProperty("/strategySpecifications") || [])];
            const implemented = this.getProperty("/implementedStrategies") || [];
            const baseStrategy = implemented.length > 0 ? implemented[0].key : "free";
            let counter = specs.length + 1;
            let strategyKey = `custom_${counter}`;
            while (specs.some(function (item) { return item.strategyKey === strategyKey; })) {
                counter += 1;
                strategyKey = `custom_${counter}`;
            }

            const newSpec = {
                strategyKey: strategyKey,
                displayName: `Custom ${counter}`,
                baseStrategy: baseStrategy,
                isolatedRounds: 0,
                peerVisibility: "named",
                promptTemplates: {
                    moderatorInstruction: "State your own position and build on relevant earlier contributions.",
                    participantInstruction: "Build directly on useful earlier points and state your own position."
                }
            };

            specs.push(newSpec);
            this.setProperty("/strategySpecifications", specs);
            this.setProperty("/strategyOptions", this._buildStrategyOptions(specs));
            this._selectStrategySpecByKey(strategyKey);
        },

        removeSelectedStrategySpecification: function () {
            this._syncSelectedStrategySpecification();
            const selectedKey = this.getProperty("/selectedStrategySpecKey");
            const implemented = this.getProperty("/implementedStrategies") || [];
            if (implemented.some(function (item) { return item.key === selectedKey; })) {
                return false;
            }
            const specs = [...(this.getProperty("/strategySpecifications") || [])];
            const index = specs.findIndex(function (item) {
                return item.strategyKey === selectedKey;
            });
            if (index === -1) {
                return;
            }

            specs.splice(index, 1);
            this.setProperty("/strategySpecifications", specs);
            this.setProperty("/strategyOptions", this._buildStrategyOptions(specs));

            const nextKey = specs.length > 0 ? specs[Math.min(index, specs.length - 1)].strategyKey : "";
            this._selectStrategySpecByKey(nextKey);
            return true;
        },

        updateSelectedStrategySpecificationField: function (field, value) {
            const selectedKey = this.getProperty("/selectedStrategySpecKey");
            if (!selectedKey) {
                return;
            }

            const specs = [...(this.getProperty("/strategySpecifications") || [])];
            const index = specs.findIndex(function (item) {
                return item.strategyKey === selectedKey;
            });
            if (index === -1) {
                return;
            }

            const current = Object.assign({}, specs[index], {
                promptTemplates: Object.assign({}, specs[index].promptTemplates || {})
            });

            if (field === "strategyKey" || field === "displayName" || field === "baseStrategy" || field === "isolatedRounds" || field === "peerVisibility") {
                current[field] = value;
            } else {
                current.promptTemplates[field] = value;
            }

            specs[index] = current;
            this.setProperty("/strategySpecifications", specs);
            this.setProperty("/strategyOptions", this._buildStrategyOptions(specs));
            this.setProperty("/selectedStrategySpecKey", current.strategyKey || "");
            this.setProperty("/selectedStrategySpec", this._cloneStrategySpecification(current));
        },

        async loadConfiguration() {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                const config = await ApiService.getConfiguration();
                const promptTemplates = {
                    global: Object.assign({}, ((config.promptTemplates || {}).global || {}))
                };
                const strategySpecifications = Array.isArray(config.strategySpecifications)
                    ? config.strategySpecifications.map(function (item) {
                        return Object.assign({}, item, {
                            peerVisibility: item.peerVisibility === "anonymous" ? "anonymous" : "named",
                            promptTemplates: Object.assign({}, item.promptTemplates || {})
                        });
                    })
                    : [];
                const implementedStrategies = Array.isArray(config.implementedStrategies)
                    ? config.implementedStrategies.map(function (item) {
                        return Object.assign({}, item);
                    })
                    : [];
                const strategyOptions = this._buildStrategyOptions(strategySpecifications);
                const selectedStrategySpecKey = strategySpecifications.length > 0
                    ? strategySpecifications[0].strategyKey
                    : "";
                this.setData(Object.assign({}, this.getData(), config, {
                    promptTemplates: promptTemplates,
                    implementedStrategies: implementedStrategies,
                    strategySpecifications: strategySpecifications,
                    strategyOptions: strategyOptions,
                    selectedStrategySpecKey: selectedStrategySpecKey,
                    selectedStrategySpec: strategySpecifications.length > 0
                        ? Object.assign({}, strategySpecifications[0], {
                            promptTemplates: Object.assign({}, strategySpecifications[0].promptTemplates || {})
                        })
                        : null,
                    selectedStrategySpecDeletable: Boolean(
                        strategySpecifications.length > 0
                        && !implementedStrategies.some(function (item) {
                            return item.key === strategySpecifications[0].strategyKey;
                        })
                    ),
                    busy: false,
                    error: null
                }));
                return config;
            } catch (oErr) {
                this.setProperty("/error", oErr.message || String(oErr));
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async saveConfiguration() {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                this._syncSelectedStrategySpecification();
                const implementedKeys = (this.getProperty("/implementedStrategies") || []).map(function (item) {
                    return item.key;
                });
                const strategySpecifications = (this.getProperty("/strategySpecifications") || []).map(function (item) {
                    return {
                        strategyKey: (item.strategyKey || "").trim(),
                        displayName: (item.displayName || "").trim(),
                        baseStrategy: (item.baseStrategy || "").trim(),
                        isolatedRounds: Number(item.isolatedRounds) || 0,
                        peerVisibility: item.peerVisibility === "anonymous" ? "anonymous" : "named",
                        promptTemplates: Object.assign({}, item.promptTemplates || {})
                    };
                });

                const keySet = new Set();
                strategySpecifications.forEach(function (item) {
                    if (!item.strategyKey) {
                        throw new Error("Each strategy specification needs a strategyKey.");
                    }
                    if (keySet.has(item.strategyKey)) {
                        throw new Error(`Duplicate strategyKey '${item.strategyKey}'.`);
                    }
                    keySet.add(item.strategyKey);
                    if (!item.displayName) {
                        throw new Error(`Strategy '${item.strategyKey}' needs a displayName.`);
                    }
                    if (!implementedKeys.includes(item.baseStrategy)) {
                        throw new Error(
                            `Strategy '${item.strategyKey}' references unknown base strategy '${item.baseStrategy}'.`
                        );
                    }
                });

                const payload = {
                    model: this.getProperty("/model"),
                    temperature: this.getProperty("/temperature"),
                    maxRounds: this.getProperty("/maxRounds"),
                    tokenLimit: this.getProperty("/tokenLimit"),
                    promptTemplates: {
                        global: this.getProperty("/promptTemplates/global") || {}
                    },
                    strategySpecifications: strategySpecifications
                };
                const saved = await ApiService.updateConfiguration(payload);
                const normalizedPromptTemplates = {
                    global: Object.assign({}, ((saved.promptTemplates || {}).global || {}))
                };
                const savedImplementedStrategies = Array.isArray(saved.implementedStrategies)
                    ? saved.implementedStrategies.map(function (item) {
                        return Object.assign({}, item);
                    })
                    : (this.getProperty("/implementedStrategies") || []).map(function (item) {
                        return Object.assign({}, item);
                    });
                const savedSpecs = Array.isArray(saved.strategySpecifications)
                    ? saved.strategySpecifications.map(function (item) {
                        return Object.assign({}, item, {
                            peerVisibility: item.peerVisibility === "anonymous" ? "anonymous" : "named",
                            promptTemplates: Object.assign({}, item.promptTemplates || {})
                        });
                    })
                    : [];
                this.setData(Object.assign({}, this.getData(), saved, {
                    promptTemplates: normalizedPromptTemplates,
                    implementedStrategies: savedImplementedStrategies,
                    strategySpecifications: savedSpecs,
                    strategyOptions: this._buildStrategyOptions(savedSpecs),
                    selectedStrategySpecKey: savedSpecs.length > 0 ? savedSpecs[0].strategyKey : "",
                    selectedStrategySpec: savedSpecs.length > 0
                        ? Object.assign({}, savedSpecs[0], {
                            promptTemplates: Object.assign({}, savedSpecs[0].promptTemplates || {})
                        })
                        : null,
                    selectedStrategySpecDeletable: Boolean(
                        savedSpecs.length > 0
                        && !savedImplementedStrategies.some(function (item) {
                            return item.key === savedSpecs[0].strategyKey;
                        })
                    ),
                    busy: false,
                    error: null
                }));
                return saved;
            } catch (oErr) {
                this.setProperty("/error", oErr.message || String(oErr));
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        }
    });
});
