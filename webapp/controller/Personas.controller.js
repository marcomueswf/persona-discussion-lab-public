sap.ui.define([
    "./BaseController",
    "sap/m/MessageBox",
    "sap/m/Dialog",
    "sap/m/Label",
    "sap/m/Input",
    "sap/m/TextArea",
    "sap/m/Button",
    "sap/m/VBox"
], function (BaseController, MessageBox, Dialog, Label, Input, TextArea, Button, VBox) {
    "use strict";

    return BaseController.extend("persona.discussion.lab.controller.Personas", {
        /**
         * Initialize the personas screen and load available personas.
         *
         * @returns {Promise<void>} Resolves after the personas are loaded.
         */
        onInit: async function () {
            this._oApiModel = this.getOwnerComponent().getModel("api");
            try {
                await this._oApiModel.loadPersonas();
            } catch (oErr) {
                this.showError(oErr);
            }
        },

        /**
         * Return the API model instance used by the personas screen.
         *
         * @returns {sap.ui.model.Model} The API model.
         */
        _getApiModel: function () {
            return this.getOwnerComponent().getModel("api");
        },

        /**
         * Navigate back to the discussion view and refresh the persona data first.
         *
         * @returns {Promise<void>} Resolves after the refresh and navigation are complete.
         */
        onBack: async function () {
            try {
                await this._getApiModel().loadPersonas();
                this.getOwnerComponent().getRouter().navTo("discussion");
            } catch (oErr) {
                this.showError(oErr);
            }
        },

        /**
         * Open a dialog for creating or updating a persona.
         *
         * @param {object} oDefaults Default values for the dialog fields.
         * @param {string} [oDefaults.personaId] Current persona ID.
         * @param {string} [oDefaults.name] Persona name.
         * @param {string} [oDefaults.role] Persona role.
         * @param {string} [oDefaults.description] Persona description.
         * @param {string} [oDefaults.systemPrompt] Legacy prompt fallback.
         * @param {string} [oDefaults.title] Dialog title.
         * @returns {Promise<object>} Resolves with the entered persona values or rejects on cancel.
         */
        _openPersonaDialog: function (oDefaults) {
            const oController = this;
            return new Promise(function (resolve, reject) {
                const oInputSettings = { width: "100%" };
                const oTextAreaSettings = { width: "100%", growing: false };
                const oIdInput = new Input(Object.assign({}, oInputSettings, { value: oDefaults.personaId || "" }));
                const oNameInput = new Input(Object.assign({}, oInputSettings, { value: oDefaults.name || "" }));
                const oRoleInput = new Input(Object.assign({}, oInputSettings, { value: oDefaults.role || "" }));
                const oDescriptionInput = new TextArea(Object.assign({}, oTextAreaSettings, { value: oDefaults.description || oDefaults.systemPrompt || "", rows: 6 }));
                const oBackgroundInput = new TextArea(Object.assign({}, oTextAreaSettings, { value: oDefaults.background || "", rows: 5 }));
                const oExpertiseInput = new Input(Object.assign({}, oInputSettings, { value: (oDefaults.expertise || []).join(", ") }));
                const oGoalsInput = new TextArea(Object.assign({}, oTextAreaSettings, { value: (oDefaults.goals || []).join(", "), rows: 5 }));
                const oConstraintsInput = new TextArea(Object.assign({}, oTextAreaSettings, { value: (oDefaults.constraints || []).join(", "), rows: 5 }));
                const oCommunicationStyleInput = new Input(Object.assign({}, oInputSettings, { value: oDefaults.communicationStyle || "" }));

                const oDialog = new Dialog({
                    title: oDefaults.title || oController.getText("personaDialogTitle"),
                    contentWidth: "90%",
                    contentHeight: "70vh",
                    stretchOnPhone: true,
                    verticalScrolling: true,
                    content: new VBox({
                        width: "100%",
                        items: [
                            new Label({ text: oController.getText("labelPersonaId"), required: true, design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oIdInput,
                            new Label({ text: oController.getText("labelName"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oNameInput,
                            new Label({ text: oController.getText("labelRole"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oRoleInput,
                            new Label({ text: oController.getText("labelDescription"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oDescriptionInput,
                            new Label({ text: oController.getText("labelBackground"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oBackgroundInput,
                            new Label({ text: oController.getText("labelExpertise"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oExpertiseInput,
                            new Label({ text: oController.getText("labelGoals"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oGoalsInput,
                            new Label({ text: oController.getText("labelConstraints"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oConstraintsInput,
                            new Label({ text: oController.getText("labelCommunicationStyle"), design: "Bold", class: "sapUiTinyMarginTop sapUiTinyMarginBegin" }),
                            oCommunicationStyleInput
                        ]
                    }),
                    beginButton: new Button({
                        text: oController.getText("buttonSave"),
                        press: function () {
                            const oResult = {
                                personaId: (oIdInput.getValue() || "").trim(),
                                name: oNameInput.getValue() || "",
                                role: oRoleInput.getValue() || "",
                                description: oDescriptionInput.getValue() || "",
                                background: oBackgroundInput.getValue() || "",
                                expertise: oExpertiseInput.getValue().split(",").map((sValue) => sValue.trim()).filter(Boolean),
                                goals: oGoalsInput.getValue().split(",").map((sValue) => sValue.trim()).filter(Boolean),
                                constraints: oConstraintsInput.getValue().split(",").map((sValue) => sValue.trim()).filter(Boolean),
                                communicationStyle: oCommunicationStyleInput.getValue() || ""
                            };
                            oDialog.close();
                            oDialog.destroy();
                            resolve(oResult);
                        }
                    }),
                    endButton: new Button({
                        text: oController.getText("buttonCancel"),
                        press: function () {
                            oDialog.close();
                            oDialog.destroy();
                            reject(new Error("aborted"));
                        }
                    }),
                    afterClose: function () {
                        // handled by resolve/reject
                    }
                });

                oDialog.open();
            });
        },

        /**
         * Creates a new persona based on the entered dialog values.
         *
         * @returns {Promise<void>} Resolves when the persona is successfully created.
         */
        onCreatePersona: async function () {
            try {
                const oNew = await this._openPersonaDialog({ title: this.getText("personaCreateDialogTitle") });
                if (!oNew.personaId) {
                    MessageBox.error(this.getText("errorPersonaIdRequired"));
                    return;
                }
                await this._getApiModel().createPersona(oNew);
            } catch (oErr) {
                if (oErr && oErr.message !== "aborted") {
                    this.showError(oErr);
                }
            }
        },

        /**
         * Updates an existing persona for the selected list entry.
         *
         * @param {sap.ui.base.Event} oEvent The event triggered by the update action.
         * @returns {Promise<void>} Resolves when the update completes.
         */
        onUpdatePersona: async function (oEvent) {
            try {
                const oCtx = oEvent.getSource().getBindingContext("api");
                if (!oCtx) {
                    MessageBox.error(this.getText("errorNoBindingContext"));
                    return;
                }
                const oCurrent = oCtx.getObject();
                const oChanges = await this._openPersonaDialog(Object.assign({ title: this.getText("personaUpdateDialogTitle") }, oCurrent));
                if (!oChanges.personaId) {
                    MessageBox.error(this.getText("errorPersonaIdRequired"));
                    return;
                }
                delete oChanges.personaId;
                await this._getApiModel().updatePersona(oCurrent.personaId, oChanges);
            } catch (oErr) {
                if (oErr && oErr.message !== "aborted") {
                    this.showError(oErr);
                }
            }
        },

        /**
         * Deletes the persona associated with the clicked list item after confirmation.
         *
         * @param {sap.ui.base.Event} oEvent The event triggered by the delete action.
         */
        onDeletePersona: function (oEvent) {
            const oCtx = oEvent.getSource().getBindingContext("api");
            if (!oCtx) {
                MessageBox.error(this.getText("errorNoBindingContext"));
                return;
            }
            const oPersona = oCtx.getObject();
            const sPersonaId = oPersona.personaId;
            const sName = oPersona.name || sPersonaId;

            MessageBox.confirm(
                this.getText("confirmDeletePersona", [sName]),
                {
                    actions: [MessageBox.Action.DELETE, MessageBox.Action.CANCEL],
                    emphasizedAction: MessageBox.Action.DELETE,
                    onClose: async (sAction) => {
                        if (sAction === MessageBox.Action.DELETE) {
                            try {
                                await this._getApiModel().deletePersona(sPersonaId);
                            } catch (oErr) {
                                this.showError(oErr);
                            }
                        }
                    }
                }
            );
        }
    });
});
