sap.ui.define([
    "sap/ui/model/json/JSONModel",
    "../service/ApiService"
], function (JSONModel, ApiService) {
    "use strict";

    return JSONModel.extend("persona.discussion.lab.model.AppModel", {
        constructor: function () {
            // initial structure as requested
            JSONModel.apply(this, [{
                personas: [],
                discussions: [],
                discussionTemplates: [],
                currentDiscussion: null,
                currentResult: null,
                currentTrace: null,
                traceBusy: false,
                traceError: null,
                busy: false,
                error: null
            }]);
        },

        async loadPersonas() {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                const aPersonas = await ApiService.getPersonas();
                // ensure array
                this.setProperty("/personas", Array.isArray(aPersonas) ? aPersonas : []);
                return aPersonas;
            } catch (oErr) {
                const sMsg = (oErr && oErr.message) ? oErr.message : String(oErr);
                this.setProperty("/error", sMsg);
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async createPersona(oPersona) {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                const oCreated = await ApiService.createPersona(oPersona);
                const aOld = this.getProperty("/personas") || [];
                const aNew = [...aOld, oCreated];
                this.setProperty("/personas", aNew);
                return oCreated;
            } catch (oErr) {
                const sMsg = (oErr && oErr.message) ? oErr.message : String(oErr);
                this.setProperty("/error", sMsg);
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async updatePersona(acPersonaId, oPersonaChanges) {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                const oUpdatedFromBackend = await ApiService.updatePersona(acPersonaId, oPersonaChanges);
                const aOld = this.getProperty("/personas") || [];
                const iIndex = aOld.findIndex(function (o) {
                    return o.personaId === acPersonaId;
                });
                if (iIndex === -1) {
                    throw new Error(`Persona with id '${acPersonaId}' not found locally`);
                }
                const oExisting = aOld[iIndex];
                // merge existing local props and backend result (backend fields override)
                const oMerged = Object.assign({}, oExisting, oUpdatedFromBackend);
                const aNew = [...aOld.slice(0, iIndex), oMerged, ...aOld.slice(iIndex + 1)];
                this.setProperty("/personas", aNew);
                return oMerged;
            } catch (oErr) {
                const sMsg = (oErr && oErr.message) ? oErr.message : String(oErr);
                this.setProperty("/error", sMsg);
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async deletePersona(acPersonaId) {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                await ApiService.deletePersona(acPersonaId);
                const aOld = this.getProperty("/personas") || [];
                const aNew = aOld.filter(function (o) {
                    return o.personaId !== acPersonaId;
                });
                this.setProperty("/personas", aNew);
                return null;
            } catch (oErr) {
                const sMsg = (oErr && oErr.message) ? oErr.message : String(oErr);
                this.setProperty("/error", sMsg);
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async startDiscussion(oRequest) {
            this.setProperty("/busy", true);
            this.setProperty("/error", null);
            try {
                const oDiscussion = await ApiService.startDiscussion(oRequest);
                this.setProperty("/currentDiscussion", oDiscussion);
                return oDiscussion;
            } catch (oErr) {
                this.setProperty("/error", oErr.message || String(oErr));
                throw oErr;
            } finally {
                this.setProperty("/busy", false);
            }
        },

        async loadDiscussion(sDiscussionId) {
            const oDiscussion = await ApiService.getDiscussion(sDiscussionId);
            this.setProperty("/currentDiscussion", oDiscussion);
            this.setProperty("/currentTrace", null);
            this.setProperty("/traceError", null);
            return oDiscussion;
        },

        async loadDiscussionTrace(sDiscussionId) {
            this.setProperty("/traceBusy", true);
            this.setProperty("/traceError", null);
            try {
                const oTrace = await ApiService.getDiscussionTrace(sDiscussionId);
                oTrace.entries = (oTrace.entries || []).map(function (oEntry) {
                    if (!oEntry.analysisOutput) {
                        return oEntry;
                    }
                    const positions = oEntry.analysisOutput.positions || {};
                    const items = oEntry.analysisOutput.items || {};
                    const basis = oEntry.analysisBasis || {};
                    const formatPercentage = function (value) {
                        return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
                    };
                    return Object.assign({}, oEntry, {
                        analysisParticipantResponses: basis.participantResponses ?? 0,
                        analysisConfiguredItemIdsText: (basis.configuredItemIds || []).join(", ") || "-",
                        analysisPositionRoundsText: Object.entries(basis.positionCountsByRound || {})
                            .map(function (round) {
                                const counts = Object.entries(round[1])
                                    .map(function (position) { return `${position[0]}: ${position[1]}`; })
                                    .join(", ");
                                return `${round[0]}: ${counts}`;
                            })
                            .join("; ") || "-",
                        analysisPositions: Object.assign({}, positions, {
                            consensusText: formatPercentage(positions.consensusLevel),
                            disagreementText: formatPercentage(positions.disagreementLevel),
                            stabilityText: formatPercentage(positions.stabilityLevel),
                            polarizationText: formatPercentage(positions.polarizationLevel),
                            minorityPositionsText: (positions.minorityPositions || []).join(", ") || "-"
                        }),
                        analysisItemEntries: Object.entries(items).map(function (entry) {
                            const metrics = entry[1];
                            return Object.assign({ itemId: entry[0] }, metrics, {
                                consensusText: formatPercentage(metrics.consensusLevel),
                                disagreementText: formatPercentage(metrics.disagreementLevel),
                                stabilityText: formatPercentage(metrics.stabilityLevel),
                                polarizationText: formatPercentage(metrics.polarizationLevel),
                                ratingDistributionText: Object.entries(metrics.ratingDistribution || {})
                                    .map(function (rating) { return `${rating[0]}: ${rating[1]}`; })
                                    .join(", ") || "-",
                                minorityRatingsText: (metrics.minorityRatings || []).join(", ") || "-"
                            });
                        })
                    });
                });
                this.setProperty("/currentTrace", oTrace);
                return oTrace;
            } catch (oErr) {
                this.setProperty("/traceError", oErr.message || String(oErr));
                throw oErr;
            } finally {
                this.setProperty("/traceBusy", false);
            }
        },

        async loadDiscussions() {
            const aDiscussions = await ApiService.getDiscussions();
            this.setProperty("/discussions", Array.isArray(aDiscussions) ? aDiscussions : []);
            return aDiscussions;
        },

        async deleteDiscussion(sDiscussionId) {
            await ApiService.deleteDiscussion(sDiscussionId);
            this.setProperty(
                "/discussions",
                (this.getProperty("/discussions") || []).filter(function (item) {
                    return item.discussionId !== sDiscussionId;
                })
            );
            if ((this.getProperty("/currentDiscussion") || {}).discussionId === sDiscussionId) {
                this.setProperty("/currentDiscussion", null);
                this.setProperty("/currentResult", null);
                this.setProperty("/currentTrace", null);
            }
        },

        async loadDiscussionTemplates() {
            const aTemplates = await ApiService.getDiscussionTemplates();
            this.setProperty("/discussionTemplates", Array.isArray(aTemplates) ? aTemplates : []);
            return aTemplates;
        },

        async loadDiscussionTemplate(sTemplateId) {
            return await ApiService.getDiscussionTemplate(sTemplateId);
        },

        async saveDiscussionTemplate(sDiscussionId, sTemplateName) {
            const oTemplate = await ApiService.saveDiscussionTemplate(sDiscussionId, sTemplateName);
            const aTemplates = this.getProperty("/discussionTemplates") || [];
            this.setProperty("/discussionTemplates", [oTemplate, ...aTemplates]);
            return oTemplate;
        },

        async deleteDiscussionTemplate(sTemplateId) {
            await ApiService.deleteDiscussionTemplate(sTemplateId);
            this.setProperty(
                "/discussionTemplates",
                (this.getProperty("/discussionTemplates") || []).filter(function (item) {
                    return item.templateId !== sTemplateId;
                })
            );
        },

        async stopDiscussion(sDiscussionId) {
            const oDiscussion = await ApiService.stopDiscussion(sDiscussionId);
            this.setProperty("/currentDiscussion", oDiscussion);
            return oDiscussion;
        },

        async loadDiscussionResult(sDiscussionId) {
            const oResult = await ApiService.getDiscussionResult(sDiscussionId);
            oResult.itemMetricEntries = Object.entries(oResult.itemMetrics || {}).map(function (entry) {
                const metric = Object.assign({ itemId: entry[0] }, entry[1]);
                metric.ratingDistributionText = Object.entries(metric.ratingDistribution || {})
                    .map(function (rating) { return `${rating[0]}: ${rating[1]}`; })
                    .join(", ");
                return metric;
            });
            this.setProperty("/currentResult", oResult);
            return oResult;
        }
    });
});
