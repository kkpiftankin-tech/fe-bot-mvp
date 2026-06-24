import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState } from "../../../test/msw";
import { useWizardStore } from "../../../store/wizardStore";
import { WizardLayout } from "../WizardLayout";

beforeEach(() => {
  useWizardStore.getState().reset();
  resetMockState();
});
afterEach(() => useWizardStore.getState().reset());

describe("WizardLayout", () => {
  it("renders all 11 steps in the navigation", () => {
    renderWithProviders(<WizardLayout />);
    expect(screen.getByText("1. Создать job")).toBeInTheDocument();
    expect(screen.getByText("2. Загрузить документы")).toBeInTheDocument();
    expect(screen.getByText("3. Парсинг документов")).toBeInTheDocument();
    expect(screen.getByText("4. Генерация RAG-карточек")).toBeInTheDocument();
    expect(screen.getByText("5. Запустить pipeline")).toBeInTheDocument();
    expect(screen.getByText("6. Проверить карточки")).toBeInTheDocument();
    expect(screen.getByText("7. Валидация metadata")).toBeInTheDocument();
    expect(screen.getByText("8. Chunking")).toBeInTheDocument();
    expect(screen.getByText("9. Retrieval-tests")).toBeInTheDocument();
    expect(screen.getByText("10. Публикация KB")).toBeInTheDocument();
    expect(screen.getByText("11. Отчёт")).toBeInTheDocument();
  });

  it("disables later steps until job is created", async () => {
    renderWithProviders(<WizardLayout />);
    const navUpload = screen.getByTestId("nav-upload");
    expect(navUpload).toHaveClass("disabled");

    // Клик по disabled нав-итему не меняет шаг.
    const user = userEvent.setup();
    await user.click(navUpload);
    expect(useWizardStore.getState().currentStep).toBe("create");
  });

  it("allows navigation between steps once job is created", async () => {
    renderWithProviders(<WizardLayout />);
    // Симулируем созданный job через store напрямую.
    useWizardStore.getState().setSetupJobId("sid_xyz", "Demo");
    // Перерисуется автоматически через подписку Zustand.
    const user = userEvent.setup();
    const navRun = await screen.findByTestId("nav-run");
    await user.click(navRun);
    expect(useWizardStore.getState().currentStep).toBe("run");
  });
});
