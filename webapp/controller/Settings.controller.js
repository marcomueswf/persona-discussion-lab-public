sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/m/MessageBox",
    "../service/ApiService"
], function (BaseController, JSONModel, MessageToast, MessageBox, ApiService) {
    "use strict";

    return BaseController.extend("persona.discussion.lab.controller.Settings", {
        /**
         * Initialize the settings screen and load the configuration model.
         *
         * @returns {Promise<void>} Resolves after the configuration is loaded.
         */
        onInit: async function () {
            const oI18nModel = this.getOwnerComponent().getModel("i18n");
            if (oI18nModel) {
                this.getView().setModel(oI18nModel, "i18n");
            }
            this._envModel = new JSONModel({
                OPENAI_API_KEY: "",
                OPENAI_BASE_URL: "",
                OPENAI_MODEL: ""
            });
            this.getView().setModel(this._envModel, "env");
            this._config = this.getOwnerComponent().getModel("config");
            if (!this._config) {
                MessageBox.error(this.getText("errorModelsNotInitialized"));
                return;
            }
            try {
                await this._config.loadConfiguration();
                await this.loadEnvironmentSettings();
            } catch (error) {
                this.showError(error);
            }
        },

        /**
         * Loads the runtime values stored in the backend .env file.
         *
         * @returns {Promise<void>} Resolves after the environment settings are retrieved.
         */
        loadEnvironmentSettings: async function () {
            const env = await ApiService.getEnvironment();
            this._envModel.setData({
                OPENAI_API_KEY: env.OPENAI_API_KEY || "",
                OPENAI_BASE_URL: env.OPENAI_BASE_URL || "",
                OPENAI_MODEL: env.OPENAI_MODEL || ""
            });
        },

        /**
         * Saves the runtime environment values to the backend .env file.
         *
         * @returns {Promise<void>} Resolves after the environment file is updated.
         */
        saveEnvironmentSettings: async function () {
            const payload = this._envModel.getData() || {};
            await ApiService.updateEnvironment(payload);
        },

        /**
         * Saves the current configuration.
         *
         * @returns {Promise<void>} Resolves after the configuration is persisted.
         */
        onSave: async function () {
            try {
                await this._config.saveConfiguration();
                await this.saveEnvironmentSettings();
                MessageToast.show(this.getText("messageConfigurationSaved"));
            } catch (error) {
                this.showError(error);
            }
        },

        /**
         * Handles a strategy specification change from a dropdown selection.
         *
         * @param {sap.ui.base.Event} oEvent The selection event.
         */
        onStrategySpecChange: function (oEvent) {
            const key = oEvent.getSource().getSelectedKey();
            this._config.selectStrategySpecification(key);
        },

        /**
         * Handles selection changes on the strategy specification list.
         *
         * @param {sap.ui.base.Event} oEvent The list selection event.
         */
        onStrategySpecSelectionChange: function (oEvent) {
            const item = oEvent.getParameter("listItem");
            if (!item) {
                return;
            }
            const context = item.getBindingContext("config");
            if (!context) {
                return;
            }
            const data = context.getObject();
            this._config.selectStrategySpecification(data.strategyKey);
        },

        /**
         * Adds a new strategy specification entry.
         */
        onAddStrategySpec: function () {
            this._config.addStrategySpecification();
        },

        /**
         * Removes the currently selected strategy specification.
         */
        onDeleteStrategySpec: function () {
            this._config.removeSelectedStrategySpecification();
        },

        /**
         * Updates the selected field in the current strategy specification.
         *
         * @param {sap.ui.base.Event} oEvent The field change event.
         */
        onSelectedSpecFieldChange: function (oEvent) {
            const source = oEvent.getSource();
            const field = source.data("field");
            if (!field) {
                return;
            }

            let value;
            if (source.isA("sap.m.Select")) {
                value = source.getSelectedKey();
            } else {
                value = oEvent.getParameter("value");
                if (value === undefined) {
                    value = source.getValue();
                }
            }

            this._config.updateSelectedStrategySpecificationField(field, value);
        },

        /**
         * Navigates back to the discussion screen.
         */
        onBack: function () {
            this.getOwnerComponent().getRouter().navTo("discussion");
        }
    });
});
