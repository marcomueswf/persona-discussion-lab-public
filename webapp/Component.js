sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/model/json/JSONModel",
    "sap/ui/model/resource/ResourceModel",
    "./model/AppModel",
    "./model/ConfigurationModel"
], function (UIComponent, JSONModel, ResourceModel, AppModel, ConfigurationModel) {
    "use strict";

    return UIComponent.extend("persona.discussion.lab.Component", {
        metadata: { manifest: "json" },

        init: function () {
            this.setModel(new ResourceModel({
                bundleName: "persona.discussion.lab.i18n.i18n"
            }), "i18n");
            UIComponent.prototype.init.apply(this, arguments);
            this.setModel(new AppModel(), "api");
            this.setModel(new ConfigurationModel(), "config");
            this.setModel(new JSONModel({
                busy: false,
                discussionRunning: false,
                discussionStopping: false,
                discussionViewMode: "discussion",
                traceEnabled: false,
                traceAllExpanded: false,
                selectedPersonaIds: [],
                selectedStrategy: "free",
                selectedStrategyUsesDelphi: false,
                selectedTemplateId: "",
                currentTopic: "",
                delphiItems: [],
                delphiRoundPlan: {},
                delphiRoundEntries: [],
                delphiRoundModes: [],
                isolatedRoundsOverrideEnabled: false,
                isolatedRoundsOverride: 0,
                roundPlan: {},
                roundPlanEntries: [],
                settings: {
                    backendUrl: "/api",
                    model: "gpt-4.1-mini",
                    temperature: 0.3,
                    maxRounds: 1,
                    tokenLimit: 1200
                }
            }), "ui");
            this.getRouter().initialize();
        }
    });
});
