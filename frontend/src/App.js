import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { getAuthHeaders, setAuthHeaders } from "./api/client";
import { WizardLayout } from "./components/Wizard/WizardLayout";
export default function App() {
    const [userId, setUserId] = useState(getAuthHeaders().userId);
    const [roles, setRoles] = useState(getAuthHeaders().roles);
    useEffect(() => {
        setAuthHeaders({ userId, roles });
    }, [userId, roles]);
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("header", { className: "app-header", children: [_jsx("h1", { children: "FE-Bot \u00B7 Setup Wizard" }), _jsxs("div", { className: "auth-info", children: [_jsx("span", { children: "X-User-Id: " }), _jsx("input", { value: userId, onChange: (e) => setUserId(e.target.value), "data-testid": "auth-user-id", style: { marginRight: 8, width: 120 } }), _jsx("span", { children: "X-Roles: " }), _jsx("input", { value: roles, onChange: (e) => setRoles(e.target.value), "data-testid": "auth-roles", style: { width: 160 } })] })] }), _jsx(WizardLayout, {})] }));
}
