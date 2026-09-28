sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/MessageBox"
], function (Controller, MessageBox) {
    "use strict";

    return Controller.extend("persona.discussion.lab.controller.BaseController", {
        /**
         * Returns a localized text from the current i18n bundle.
         *
         * @param {string} sKey The translation key.
         * @param {string[]} [aArgs] Optional interpolation arguments.
         * @returns {string} The localized text.
         */
        getText: function (sKey, aArgs) {
            const oViewModel = this.getView && this.getView() ? this.getView().getModel("i18n") : null;
            const oComponentModel = this.getOwnerComponent ? this.getOwnerComponent().getModel("i18n") : null;
            const oI18nModel = oViewModel || oComponentModel;

            if (!oI18nModel || !oI18nModel.getResourceBundle) {
                return sKey;
            }

            return oI18nModel.getResourceBundle().getText(sKey, aArgs || []);
        },

        /**
         * Displays a standard error message dialog for an exception-like value.
         *
         * @param {Error|string|unknown} error The error or message to display.
         */
        showError: function (error) {
            const message = error && error.message ? error.message : String(error);
            MessageBox.error(message);
        }
    });
});
