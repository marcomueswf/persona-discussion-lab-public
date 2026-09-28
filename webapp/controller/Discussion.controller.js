sap.ui.define([
    "./BaseController",
    "sap/m/MessageBox",
    "sap/m/Dialog",
    "sap/m/Input",
    "sap/m/Button"
], function (BaseController, MessageBox, Dialog, Input, Button) {
    "use strict";

    return BaseController.extend("persona.discussion.lab.controller.Discussion", {
        /**
         * Initialize the controller and load all required models and data.
         *
         * @returns {Promise<void>} A promise that resolves when the initial data is loaded.
         */
        onInit: async function () {
            this._api = this.getOwnerComponent().getModel("api");
            this._ui = this.getOwnerComponent().getModel("ui");
            this._config = this.getOwnerComponent().getModel("config");
            if (!this._api || !this._ui || !this._config) {
                MessageBox.error(this.getText("errorModelsNotInitialized"));
                return;
            }
            try {
                await Promise.all([
                    this._api.loadPersonas(),
                    this._config.loadConfiguration(),
                    this._api.loadDiscussions(),
                    this._api.loadDiscussionTemplates()
                ]);
                this._ui.setProperty("/delphiItems", this._getDefaultDelphiItems());
                this._ui.setProperty("/delphiRoundModes", this._getDelphiRoundModes());
                this._ui.setProperty("/delphiRoundPlan", this._createDefaultDelphiRoundPlan());
                const options = this._config.getProperty("/strategyOptions") || [];
                const current = this._ui.getProperty("/selectedStrategy");
                const exists = options.some(function (item) {
                    return item.key === current;
                });
                if (!exists && options.length > 0) {
                    this._ui.setProperty("/selectedStrategy", options[0].key);
                }
                this._updateSelectedStrategyMode();
                this._refreshRoundPlanEntries();
                this._refreshDelphiRoundEntries();
            } catch (error) {
                this.showError(error);
            }
        },

        /**
         * Rebuilds the round-plan entry list to match the currently configured round count.
         *
         * The round-plan editor never assumes a fixed round count; it always mirrors
         * the effective maxRounds value from the configuration model.
         */
        _refreshRoundPlanEntries: function () {
            const maxRounds = Number(this._config.getProperty("/maxRounds")) || 0;
            const entries = [];
            for (let index = 1; index <= maxRounds; index += 1) {
                entries.push({ index: index, field: `participantInstructionRound${index}` });
            }
            this._ui.setProperty("/roundPlanEntries", entries);
        },

        _isDelphiStrategy: function (strategyKey) {
            if (strategyKey === "delphi") {
                return true;
            }
            return (this._config.getProperty("/strategySpecifications") || []).some(function (specification) {
                return specification.strategyKey === strategyKey && specification.baseStrategy === "delphi";
            });
        },

        _updateSelectedStrategyMode: function () {
            const strategyKey = this._ui.getProperty("/selectedStrategy");
            this._ui.setProperty("/selectedStrategyUsesDelphi", this._isDelphiStrategy(strategyKey));
        },

        onStrategyChange: function () {
            this._updateSelectedStrategyMode();
        },

        _getDefaultDelphiItems: function () {
            return (this._config.getProperty("/delphiItems") || [])
                .filter(function (item) { return item.status !== "inactive"; })
                .map(function (item) { return Object.assign({}, item); });
        },

        _getDelphiRoundModes: function () {
            return [
                { key: "open", text: this.getText("delphiRoundModeOpen") },
                { key: "rate", text: this.getText("delphiRoundModeRate") },
                { key: "discuss", text: this.getText("delphiRoundModeDiscuss") },
                { key: "most_disputed", text: this.getText("delphiRoundModeMostDisputed") },
                { key: "synthesize", text: this.getText("delphiRoundModeSynthesize") }
            ];
        },

        _defaultDelphiRoundConfiguration: function (roundIndex) {
            const itemIds = (this._ui.getProperty("/delphiItems") || []).map(function (item) { return item.itemId; });
            let mode = "synthesize";
            if (roundIndex === 1) {
                mode = "open";
            } else if (roundIndex === 2) {
                mode = itemIds.length ? "rate" : "open";
            } else if (roundIndex === 3) {
                mode = itemIds.length ? "most_disputed" : "open";
            }
            return {
                mode: mode,
                itemIds: mode === "rate" || mode === "discuss" ? itemIds : []
            };
        },

        _createDefaultDelphiRoundPlan: function () {
            const maxRounds = Number(this._config.getProperty("/maxRounds")) || 1;
            const plan = {};
            for (let roundIndex = 1; roundIndex <= maxRounds; roundIndex += 1) {
                plan[roundIndex] = this._defaultDelphiRoundConfiguration(roundIndex);
            }
            return plan;
        },

        _refreshDelphiRoundEntries: function () {
            const maxRounds = Number(this._config.getProperty("/maxRounds")) || 1;
            const plan = Object.assign({}, this._ui.getProperty("/delphiRoundPlan") || {});
            const entries = [];
            for (let roundIndex = 1; roundIndex <= maxRounds; roundIndex += 1) {
                const key = String(roundIndex);
                const configuration = Object.assign(
                    {},
                    plan[key] || plan[roundIndex] || this._defaultDelphiRoundConfiguration(roundIndex)
                );
                configuration.itemIds = Array.isArray(configuration.itemIds) ? configuration.itemIds : [];
                plan[key] = configuration;
                entries.push({ index: roundIndex, key: key, mode: configuration.mode, itemIds: configuration.itemIds });
            }
            Object.keys(plan).forEach(function (key) {
                if (Number(key) > maxRounds) {
                    delete plan[key];
                }
            });
            this._ui.setProperty("/delphiRoundPlan", plan);
            this._ui.setProperty("/delphiRoundEntries", entries);
        },

        onDelphiRoundModeChange: function (event) {
            const roundKey = event.getSource().data("round");
            const plan = Object.assign({}, this._ui.getProperty("/delphiRoundPlan") || {});
            const configuration = Object.assign({}, plan[roundKey] || {});
            configuration.mode = event.getSource().getSelectedKey();
            if (configuration.mode === "rate" && !(configuration.itemIds || []).length) {
                configuration.itemIds = (this._ui.getProperty("/delphiItems") || []).map(function (item) {
                    return item.itemId;
                });
            }
            plan[roundKey] = configuration;
            this._ui.setProperty("/delphiRoundPlan", plan);
            this._refreshDelphiRoundEntries();
        },

        onDelphiRoundItemsChange: function (event) {
            const roundKey = event.getSource().data("round");
            const plan = Object.assign({}, this._ui.getProperty("/delphiRoundPlan") || {});
            const configuration = Object.assign({}, plan[roundKey] || {});
            configuration.itemIds = event.getSource().getSelectedKeys();
            plan[roundKey] = configuration;
            this._ui.setProperty("/delphiRoundPlan", plan);
            this._refreshDelphiRoundEntries();
        },

        _syncDelphiRoundItems: function (addedItemId) {
            const validIds = new Set((this._ui.getProperty("/delphiItems") || []).map(function (item) {
                return item.itemId;
            }));
            const plan = Object.assign({}, this._ui.getProperty("/delphiRoundPlan") || {});
            Object.keys(plan).forEach(function (roundKey) {
                if (["rate", "discuss"].includes(plan[roundKey].mode)) {
                    const itemIds = (plan[roundKey].itemIds || []).filter(function (itemId) {
                        return validIds.has(itemId);
                    });
                    if (addedItemId && plan[roundKey].mode === "rate") {
                        itemIds.push(addedItemId);
                    }
                    plan[roundKey] = Object.assign({}, plan[roundKey], {
                        itemIds: itemIds
                    });
                }
            });
            this._ui.setProperty("/delphiRoundPlan", plan);
            this._refreshDelphiRoundEntries();
        },

        _newDelphiItemId: function () {
            if (window.crypto && typeof window.crypto.randomUUID === "function") {
                return `delphi-${window.crypto.randomUUID()}`;
            }
            this._delphiItemIdCounter = (this._delphiItemIdCounter || 0) + 1;
            return `delphi-${Date.now()}-${this._delphiItemIdCounter}`;
        },

        onAddDelphiItem: function () {
            const items = (this._ui.getProperty("/delphiItems") || []).slice();
            const itemId = this._newDelphiItemId();
            items.push({
                itemId: itemId,
                statement: "",
                scaleMin: 1,
                scaleMax: 5,
                status: "active"
            });
            this._ui.setProperty("/delphiItems", items);
            this._syncDelphiRoundItems(itemId);
        },

        onRemoveDelphiItem: function (event) {
            const itemId = event.getSource().data("itemId");
            const items = (this._ui.getProperty("/delphiItems") || [])
                .filter(function (item) { return item.itemId !== itemId; });
            this._ui.setProperty("/delphiItems", items);
            this._syncDelphiRoundItems();
        },

        /**
         * Reads one round-plan value for display in the round-plan editor.
         *
         * @param {object} roundPlan The current topic-scoped round plan.
         * @param {string} field The round-specific field name, e.g. "participantInstructionRound2".
         * @returns {string} The current override text, or an empty string when unset.
         */
        formatRoundPlanValue: function (roundPlan, field) {
            return (roundPlan && field && roundPlan[field]) || "";
        },

        /**
         * Hides structured JSON that some model responses append to the prose.
         * The raw content remains available in the API model and is not changed.
         *
         * @param {string} content Rendered participant contribution.
         * @returns {string} Contribution text without a trailing structured payload.
         */
        formatContributionContent: function (content) {
            if (typeof content !== "string") {
                return content || "";
            }
            return content
                .replace(/\s*```json\s*\{[\s\S]*?\}\s*```\s*$/i, "")
                .replace(/\s*\{\s*"(?:position|rating|confidence|revised|itemId)"[\s\S]*\}\s*$/i, "")
                .trim();
        },

        /**
         * Updates one round-plan field from the round-plan editor.
         *
         * @param {sap.ui.base.Event} oEvent The field change event.
         */
        onRoundPlanFieldChange: function (oEvent) {
            const field = oEvent.getSource().data("field");
            if (!field) {
                return;
            }
            const value = oEvent.getParameter("value");
            const roundPlan = Object.assign({}, this._ui.getProperty("/roundPlan") || {});
            roundPlan[field] = value;
            this._ui.setProperty("/roundPlan", roundPlan);
        },

        /**
         * Starts a new discussion with the selected topic, personas, and strategy.
         *
         * @returns {Promise<void>} Resolves once the discussion has been started or an error is shown.
         */
        onStart: async function () {
            const topic = (this._ui.getProperty("/currentTopic") || "").trim();
            const personaIds = this._ui.getProperty("/selectedPersonaIds") || [];
            const selectedStrategy = this._ui.getProperty("/selectedStrategy");
            const strategyOptions = this._config.getProperty("/strategyOptions") || [];
            const hasStrategy = strategyOptions.some(function (item) {
                return item.key === selectedStrategy;
            });
            if (!topic || personaIds.length < 2) {
                MessageBox.warning(this.getText("warningTopicAndPersonas"));
                return;
            }
            if (!hasStrategy) {
                MessageBox.warning(this.getText("warningChooseValidStrategy"));
                return;
            }
            const delphiItems = this._ui.getProperty("/delphiItems") || [];
            const usesDelphi = this._isDelphiStrategy(selectedStrategy);
            if (usesDelphi) {
                const statements = delphiItems.map(function (item) {
                    return (item.statement || "").trim().toLowerCase();
                });
                if (statements.some(function (statement) { return !statement; })
                    || new Set(statements).size !== statements.length) {
                    MessageBox.warning(this.getText("warningDelphiItemsInvalid"));
                    return;
                }
                const roundPlan = this._ui.getProperty("/delphiRoundPlan") || {};
                const hasEmptyItemRound = Object.keys(roundPlan).some(function (roundKey) {
                    const configuration = roundPlan[roundKey];
                    return ["rate", "discuss"].includes(configuration.mode)
                        && (!configuration.itemIds || configuration.itemIds.length === 0);
                });
                if (hasEmptyItemRound) {
                    MessageBox.warning(this.getText("warningDelphiRoundItemsRequired"));
                    return;
                }
            }
            this._ui.setProperty("/discussionRunning", true);
            this._ui.setProperty("/discussionStopping", false);
            try {
                const request = {
                    topic: topic,
                    personaIds: personaIds,
                    strategy: selectedStrategy,
                    temperature: this._config.getProperty("/temperature"),
                    maxRounds: this._config.getProperty("/maxRounds"),
                    tokenLimit: this._config.getProperty("/tokenLimit"),
                    traceEnabled: this._ui.getProperty("/traceEnabled") === true,
                    roundPlan: this._ui.getProperty("/roundPlan") || {}
                };
                if (usesDelphi) {
                    request.delphiItems = delphiItems.map(function (item) {
                        return {
                            itemId: item.itemId,
                            statement: item.statement.trim(),
                            scaleMin: 1,
                            scaleMax: 5,
                            status: "active"
                        };
                    });
                    request.delphiRoundPlan = this._ui.getProperty("/delphiRoundPlan") || {};
                }
                if (this._ui.getProperty("/isolatedRoundsOverrideEnabled") === true) {
                    request.isolatedRounds = Number(this._ui.getProperty("/isolatedRoundsOverride")) || 0;
                }
                const discussion = await this._api.startDiscussion(request);
                this._ui.setProperty("/discussionViewMode", "discussion");
                this._poll(discussion.discussionId);
            } catch (error) {
                this._ui.setProperty("/discussionRunning", false);
                this.showError(error);
            }
        },

        /**
         * Stops the currently active discussion.
         *
         * @returns {Promise<void>} Resolves when the stop request is handled.
         */
        onStop: async function () {
            const discussion = this._api.getProperty("/currentDiscussion");
            if (!discussion || this._ui.getProperty("/discussionStopping")) {
                return;
            }

            this._ui.setProperty("/discussionStopping", true);
            try {
                await this._api.stopDiscussion(discussion.discussionId);
            } catch (error) {
                this._ui.setProperty("/discussionStopping", false);
                this.showError(error);
            }
        },

        /**
         * Opens the dialog to save the current discussion as a reusable template.
         */
        onSaveTemplate: function () {
            const discussion = this._api.getProperty("/currentDiscussion");
            if (!discussion || !["completed", "stopped"].includes(discussion.status)) {
                return;
            }

            const input = new Input({
                placeholder: this.getText("templateNamePlaceholder"),
                width: "100%"
            });
            const dialog = new Dialog({
                title: this.getText("saveTemplateDialogTitle"),
                content: [input],
                beginButton: new Button({
                    text: this.getText("buttonSave"),
                    type: "Emphasized",
                    press: async () => {
                        const name = input.getValue().trim();
                        if (!name) {
                            MessageBox.warning(this.getText("warningTemplateNameRequired"));
                            return;
                        }
                        try {
                            await this._api.saveDiscussionTemplate(discussion.discussionId, name);
                            MessageBox.success(this.getText("messageTemplateSaved"));
                            dialog.close();
                        } catch (error) {
                            this.showError(error);
                        }
                    }
                }),
                endButton: new Button({
                    text: this.getText("buttonCancel"),
                    press: () => dialog.close()
                }),
                afterClose: () => dialog.destroy()
            });
            dialog.open();
        },

        /**
         * Applies the selected discussion template to the current UI state.
         *
         * @param {sap.ui.base.Event} event The selection event from the template dropdown.
         * @returns {Promise<void>} Resolves after the template has been loaded and applied.
         */
        onTemplateSelected: async function (event) {
            const templateId = event.getSource().getSelectedKey();
            this._ui.setProperty("/selectedTemplateId", templateId || "");
            if (!templateId) {
                return;
            }
            try {
                const template = await this._api.loadDiscussionTemplate(templateId);
                this._applyTemplate(template);
            } catch (error) {
                this.showError(error);
            }
        },

        /**
         * Deletes the currently selected template after confirmation.
         */
        onDeleteTemplate: function () {
            const templateId = this._ui.getProperty("/selectedTemplateId");
            if (!templateId) {
                return;
            }

            MessageBox.confirm(this.getText("confirmDeleteTemplate"), {
                onClose: async (action) => {
                    if (action !== MessageBox.Action.OK) {
                        return;
                    }
                    try {
                        await this._api.deleteDiscussionTemplate(templateId);
                        this._ui.setProperty("/selectedTemplateId", "");
                    } catch (error) {
                        this.showError(error);
                    }
                }
            });
        },

        /**
         * Deletes the current discussion after confirmation if it is not running.
         */
        onDeleteDiscussion: function () {
            const discussion = this._api.getProperty("/currentDiscussion");
            if (!discussion || ["queued", "running"].includes(discussion.status)) {
                return;
            }

            MessageBox.confirm(this.getText("confirmDeleteDiscussion"), {
                onClose: async (action) => {
                    if (action !== MessageBox.Action.OK) {
                        return;
                    }
                    try {
                        await this._api.deleteDiscussion(discussion.discussionId);
                    } catch (error) {
                        this.showError(error);
                    }
                }
            });
        },

        /**
         * Loads a discussion from the selected list entry and applies its data to the UI.
         *
         * @param {sap.ui.base.Event} event The selection event from the discussion list.
         * @returns {Promise<void>} Resolves when the discussion details have been loaded.
         */
        onDiscussionSelected: async function (event) {
            const discussionId = event.getSource().getSelectedKey();
            if (!discussionId) {
                return;
            }
            try {
                const discussion = await this._api.loadDiscussion(discussionId);
                this._ui.setProperty("/currentTopic", discussion.topic || "");
                this._ui.setProperty("/selectedPersonaIds", discussion.personaIds || []);
                this._ui.setProperty("/selectedStrategy", discussion.strategy || "");
            } catch (error) {
                this.showError(error);
            }
        },

        onDiscussionViewModeChange: async function (event) {
            const sMode = event.getParameter("item").getKey();
            this._ui.setProperty("/discussionViewMode", sMode);
            if (sMode !== "trace") {
                return;
            }
            const oDiscussion = this._api.getProperty("/currentDiscussion");
            if (!oDiscussion) {
                return;
            }
            try {
                await this._api.loadDiscussionTrace(oDiscussion.discussionId);
            } catch (oErr) {
                this._ui.setProperty("/discussionViewMode", "discussion");
                this.showError(oErr);
            }
        },

        /**
         * Toggles all LLM trace entry panels between expanded and collapsed.
         */
        onToggleTraceExpansion: function () {
            const expanded = this._ui.getProperty("/traceAllExpanded");
            this._ui.setProperty("/traceAllExpanded", !expanded);
        },

        /**
         * Downloads the currently displayed view (discussion or LLM trace) as a text file.
         */
        onDownloadDiscussion: function () {
            const discussion = this._api.getProperty("/currentDiscussion");
            if (!discussion) {
                return;
            }
            const mode = this._ui.getProperty("/discussionViewMode");
            const isTrace = mode === "trace";
            const content = isTrace ? this._buildTraceText(discussion) : this._buildDiscussionText(discussion);
            const suffix = isTrace ? "trace" : "discussion";
            const fileName = `${discussion.discussionId || "discussion"}-${suffix}.txt`;
            this._triggerTextDownload(fileName, content);
        },

        /**
         * Builds a plain-text export of the discussion topic, messages, and summary.
         *
         * @param {object} discussion The current discussion object from the API model.
         * @returns {string} The formatted text content.
         */
        _buildDiscussionText: function (discussion) {
            const lines = [];
            lines.push(`Topic: ${discussion.topic || ""}`);
            lines.push(`Status: ${discussion.status || ""}`);
            lines.push("");
            (discussion.messages || []).forEach((message) => {
                lines.push(`[${message.personaName || ""}]`);
                lines.push(message.content || "");
                lines.push("");
            });
            if (discussion.summary) {
                lines.push("Result:");
                lines.push(discussion.summary);
            }
            return lines.join("\n");
        },

        /**
         * Builds a plain-text export of the LLM trace entries for the current discussion.
         *
         * @param {object} discussion The current discussion object from the API model.
         * @returns {string} The formatted text content.
         */
        _buildTraceText: function (discussion) {
            const trace = this._api.getProperty("/currentTrace");
            const lines = [];
            lines.push(`Topic: ${discussion.topic || ""}`);
            lines.push("");
            (trace && trace.entries || []).forEach((entry) => {
                lines.push(`${entry.sequence}. ${entry.callType} - ${entry.personaName || "system"}`);
                lines.push(`Round: ${entry.roundIndex || "-"} | Status: ${entry.status}`);
                lines.push(`Duration: ${entry.durationMs || 0} ms`);
                lines.push("System prompt:");
                lines.push(entry.systemPrompt || "");
                lines.push("User prompt:");
                lines.push(entry.userPrompt || "");
                lines.push("Response:");
                lines.push(entry.response || "");
                if (entry.analysisBasis) {
                    lines.push("Analyzer input summary:");
                    lines.push(JSON.stringify(entry.analysisBasis, null, 2));
                }
                if (entry.analysisOutput) {
                    lines.push("Analyzer output:");
                    lines.push(JSON.stringify(entry.analysisOutput, null, 2));
                }
                if (entry.error) {
                    lines.push("Error:");
                    lines.push(entry.error);
                }
                lines.push("");
            });
            return lines.join("\n");
        },

        /**
         * Triggers a browser download of the given text content as a .txt file.
         *
         * @param {string} fileName The name of the file to download.
         * @param {string} content The text content to download.
         */
        _triggerTextDownload: function (fileName, content) {
            // BOM so Notepad and other tools detect UTF-8 instead of guessing ANSI for umlauts.
            const blob = new Blob(["\ufeff" + content], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = fileName;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            URL.revokeObjectURL(url);
        },

        /**
         * Applies a loaded template to the current discussion form values.
         *
         * @param {object} template The template object from the backend.
         * @param {string} [template.topic] The topic text.
         * @param {string[]} [template.personaIds] Persona IDs to select.
         * @param {string} [template.strategy] Selected strategy.
         * @param {object} [template.configuration] Template configuration values.
         * @returns {void}
         */
        _applyTemplate: function (template) {
            this._ui.setProperty("/currentTopic", template.topic || "");
            this._ui.setProperty("/selectedPersonaIds", template.personaIds || []);
            this._ui.setProperty("/selectedStrategy", template.strategy || "");
            this._updateSelectedStrategyMode();
            if (template.configuration) {
                ["model", "temperature", "maxRounds", "tokenLimit"].forEach((key) => {
                    if (template.configuration[key] !== undefined) {
                        this._config.setProperty(`/${key}`, template.configuration[key]);
                    }
                });
                this._ui.setProperty("/roundPlan", Object.assign({}, template.configuration.roundPlan || {}));
                if (Array.isArray(template.configuration.delphiItems)) {
                    this._ui.setProperty("/delphiItems", template.configuration.delphiItems.map(function (item) {
                        return Object.assign({}, item);
                    }));
                }
                if (template.configuration.delphiRoundPlan) {
                    this._ui.setProperty("/delphiRoundPlan", Object.assign({}, template.configuration.delphiRoundPlan));
                } else {
                    this._ui.setProperty("/delphiRoundPlan", this._createDefaultDelphiRoundPlan());
                }
            } else {
                this._ui.setProperty("/roundPlan", {});
                this._ui.setProperty("/delphiRoundPlan", this._createDefaultDelphiRoundPlan());
            }
            this._refreshRoundPlanEntries();
            this._refreshDelphiRoundEntries();
        },

        /**
         * Navigates to a route based on the clicked control data.
         *
         * @param {sap.ui.base.Event} event The navigation event.
         */
        onNavigate: function (event) {
            this.getOwnerComponent().getRouter().navTo(event.getSource().data("route"));
        },

        /**
         * Polls the backend for the current discussion state until it concludes.
         *
         * @param {string} discussionId The discussion ID to track.
         * @returns {void}
         */
        _poll: function (discussionId) {
            clearInterval(this._pollTimer);
            this._pollTimer = setInterval(async () => {
                try {
                    const discussion = await this._api.loadDiscussion(discussionId);
                    if (["completed", "stopped", "failed"].includes(discussion.status)) {
                        clearInterval(this._pollTimer);
                        this._ui.setProperty("/discussionRunning", false);
                        this._ui.setProperty("/discussionStopping", false);
                        if (discussion.status === "completed" || discussion.status === "stopped") {
                            await this._api.loadDiscussionResult(discussionId);
                            await this._api.loadDiscussions();
                        }
                    }
                } catch (error) {
                    clearInterval(this._pollTimer);
                    this._ui.setProperty("/discussionRunning", false);
                    this.showError(error);
                }
            }, 1000);
        },

        /**
         * Clears the polling timer when the controller is destroyed.
         */
        onExit: function () {
            clearInterval(this._pollTimer);
        }
    });
});
