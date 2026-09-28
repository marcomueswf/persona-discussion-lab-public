sap.ui.define([], function () {
    "use strict";

    const oLocation = window.location;
    // Force IPv4 loopback in dev: the backend only binds 127.0.0.1, but the
    // dev server may be opened via "localhost", which can resolve to the
    // IPv6 loopback (::1) and cause fetch failures even though the backend
    // is running.
    const sDevApiOrigin = oLocation.port === "8080"
        ? `${oLocation.protocol}//127.0.0.1:8000`
        : "";
    const BASE_URL = `${sDevApiOrigin}/api`;

    async function request(acPath, oOptions = {}) {
        const sUrl = `${BASE_URL}${acPath}`;
        const oDefaultHeaders = {
            "Accept": "application/json"
        };

        const oHeaders = Object.assign({}, oDefaultHeaders, oOptions.headers || {});

        // If body present and no explicit content-type, set json
        if (oOptions.body !== undefined && oHeaders["Content-Type"] === undefined) {
            oHeaders["Content-Type"] = "application/json";
        }

        const oFetchOptions = Object.assign({}, oOptions, { headers: oHeaders });

        let oResponse;
        try {
            oResponse = await fetch(sUrl, oFetchOptions);
        } catch (oErr) {
            // Network / CORS / other
            throw new Error(`Network error while calling ${sUrl}: ${oErr.message || oErr}`);
        }

        // 204 No Content -> return null
        if (oResponse.status === 204) {
            return null;
        }

        // Try read body as text and parse JSON when possible
        let vBody = null;
        const sText = await oResponse.text();
        if (sText) {
            try {
                vBody = JSON.parse(sText);
            } catch (e) {
                // not JSON, keep text
                vBody = sText;
            }
        }

        if (!oResponse.ok) {
            // Try to extract a useful message
            let sMessage = oResponse.statusText || `HTTP ${oResponse.status}`;
            if (vBody && typeof vBody === "object") {
                sMessage = vBody.detail || vBody.message || JSON.stringify(vBody);
            } else if (typeof vBody === "string" && vBody.length) {
                sMessage = vBody;
            }
            const oError = new Error(`${oResponse.status} ${sMessage}`);
            oError.status = oResponse.status;
            oError.body = vBody;
            throw oError;
        }

        // Successful -> return parsed JSON or raw text
        return vBody;
    }

    return {
        async getPersonas() {
            return await request("/personas", {
                method: "GET"
            });
        },

        async createPersona(oPersona) {
            return await request("/personas", {
                method: "POST",
                body: JSON.stringify(oPersona)
            });
        },

        async updatePersona(acPersonaId, oPersonaChanges) {
            const sId = encodeURIComponent(acPersonaId);
            return await request(`/personas/${sId}`, {
                method: "PATCH",
                body: JSON.stringify(oPersonaChanges)
            });
        },

        async deletePersona(acPersonaId) {
            const sId = encodeURIComponent(acPersonaId);
            return await request(`/personas/${sId}`, {
                method: "DELETE"
            });
        },

        async startDiscussion(oRequest) {
            return await request("/discussions", {
                method: "POST",
                body: JSON.stringify(oRequest)
            });
        },

        async getDiscussion(sDiscussionId) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}`, {
                method: "GET"
            });
        },

        async getDiscussionTrace(sDiscussionId) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}/trace`, {
                method: "GET"
            });
        },

        async deleteDiscussion(sDiscussionId) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}`, {
                method: "DELETE"
            });
        },

        async stopDiscussion(sDiscussionId) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}/stop`, {
                method: "POST"
            });
        },

        async getDiscussions() {
            return await request("/discussions", {
                method: "GET"
            });
        },

        async getDiscussionTemplates() {
            return await request("/discussion-templates", {
                method: "GET"
            });
        },

        async getDiscussionTemplate(sTemplateId) {
            return await request(`/discussion-templates/${encodeURIComponent(sTemplateId)}`, {
                method: "GET"
            });
        },

        async saveDiscussionTemplate(sDiscussionId, sTemplateName) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}/template`, {
                method: "POST",
                body: JSON.stringify({
                    discussionId: sDiscussionId,
                    templateName: sTemplateName
                })
            });
        },

        async deleteDiscussionTemplate(sTemplateId) {
            return await request(`/discussion-templates/${encodeURIComponent(sTemplateId)}`, {
                method: "DELETE"
            });
        },

        async getConfiguration() {
            return await request("/configuration", {
                method: "GET"
            });
        },

        async updateConfiguration(oChanges) {
            return await request("/configuration", {
                method: "PATCH",
                body: JSON.stringify(oChanges)
            });
        },

        async getEnvironment() {
            return await request("/env", {
                method: "GET"
            });
        },

        async updateEnvironment(oChanges) {
            return await request("/env", {
                method: "PATCH",
                body: JSON.stringify(oChanges)
            });
        },

        async getDiscussionResult(sDiscussionId) {
            return await request(`/discussions/${encodeURIComponent(sDiscussionId)}/result`, {
                method: "GET"
            });
        }
    };
});
