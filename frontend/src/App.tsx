import { useEffect, useState } from "react";
import { getAuthHeaders, setAuthHeaders } from "./api/client";
import { WizardLayout } from "./components/Wizard/WizardLayout";

export default function App(): JSX.Element {
  const [userId, setUserId] = useState(getAuthHeaders().userId);
  const [roles, setRoles] = useState(getAuthHeaders().roles);

  useEffect(() => {
    setAuthHeaders({ userId, roles });
  }, [userId, roles]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>FE-Bot · Setup Wizard</h1>
        <div className="auth-info">
          <span>X-User-Id: </span>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            data-testid="auth-user-id"
            style={{ marginRight: 8, width: 120 }}
          />
          <span>X-Roles: </span>
          <input
            value={roles}
            onChange={(e) => setRoles(e.target.value)}
            data-testid="auth-roles"
            style={{ width: 160 }}
          />
        </div>
      </header>
      <WizardLayout />
    </div>
  );
}
