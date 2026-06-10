import { jsx as _jsx } from "react/jsx-runtime";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
export function renderWithProviders(ui, options = {}) {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false, refetchOnWindowFocus: false, gcTime: 0 },
            mutations: { retry: false },
        },
    });
    const Wrapper = ({ children }) => (_jsx(QueryClientProvider, { client: queryClient, children: children }));
    return render(ui, { wrapper: Wrapper, ...options });
}
