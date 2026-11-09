import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { resetMockState } from "../../../test/msw";
import { useWizardStore } from "../../../store/wizardStore";
import { ClassifierLibraryStep } from "../steps/ClassifierLibraryStep";

beforeEach(() => {
  useWizardStore.getState().reset();
  resetMockState();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => {
  useWizardStore.getState().reset();
  vi.restoreAllMocks();
});

describe("ClassifierLibraryStep (SETUP-13 / ADR-HTC-09)", () => {
  it("loads the tree root expanded by default and selects it for editing", async () => {
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");
    expect(screen.getByTestId("classifier-node-name")).toHaveValue("АСУ");

    // Корень раскрыт по умолчанию — дети видны сразу в дереве, без
    // перехода "внутрь" (тест на регресс UX).
    expect(screen.getByTestId("classifier-tree-node-cls-a")).toHaveTextContent("Класс A");
    expect(screen.getByTestId("classifier-tree-node-cls-b")).toHaveTextContent("Класс B");
    // Корень нельзя удалить.
    expect(screen.queryByTestId("classifier-node-delete")).not.toBeInTheDocument();
  });

  it("expands a branch in place (accordion) on a single click, without losing tree context", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");

    // Один клик по строке "Класс B" одновременно раскрывает её и выбирает
    // узел — так что раскрытие срабатывает при клике в любом месте строки,
    // а не только при попадании точно по маленькой стрелке.
    await user.click(screen.getByTestId("classifier-tree-node-cls-b"));
    await screen.findByTestId("classifier-tree-node-cls-b-1");
    // Дерево остаётся на экране целиком — "Класс A" по-прежнему виден.
    expect(screen.getByTestId("classifier-tree-node-cls-a")).toBeInTheDocument();
    expect(screen.getByTestId("classifier-tree")).toBeInTheDocument();

    await screen.findByDisplayValue("Класс B");
    expect(screen.getByTestId("classifier-node-breadcrumb")).toHaveTextContent(
      "АСУ › Класс B",
    );

    const nameInput = screen.getByTestId("classifier-node-name");
    await user.clear(nameInput);
    await user.type(nameInput, "Класс B (переименован)");
    await user.click(screen.getByTestId("classifier-node-save"));

    await waitFor(() =>
      expect(screen.getByTestId("classifier-tree-node-cls-b")).toHaveTextContent(
        "Класс B (переименован)",
      ),
    );

    // Повторный клик по той же строке сворачивает её обратно.
    await user.click(screen.getByTestId("classifier-tree-node-cls-b"));
    await waitFor(() =>
      expect(screen.queryByTestId("classifier-tree-node-cls-b-1")).not.toBeInTheDocument(),
    );
  });

  it("shows a single editable field pre-filled with the real (non-empty) prompt, without the unused fragment placeholder", async () => {
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");

    const promptField = screen.getByTestId<HTMLTextAreaElement>("classifier-node-prompt");
    expect(promptField).toBeVisible();
    // Поле не пустое — содержит реальный промпт, а не placeholder-заглушку.
    expect(promptField.value).toContain("АСУ");
    // Секция с текстом фрагмента — техническая обвязка реального вызова
    // классификации, при редактировании промпта её быть не должно.
    expect(promptField.value).not.toContain("fragment_text");
    expect(promptField.value).not.toContain("BEGIN_FRAGMENT");
  });

  it("drafts a description via LLM into the (unsaved) description field", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");

    const descriptionField = screen.getByTestId<HTMLTextAreaElement>(
      "classifier-node-description",
    );
    expect(descriptionField).toHaveValue("");

    await user.click(screen.getByTestId("classifier-node-generate-description"));
    await waitFor(() =>
      expect(descriptionField.value).toContain("Черновик описания для «АСУ»"),
    );
    // Черновик не сохранён сам по себе — нужна явная "Сохранить".
    await user.click(screen.getByTestId("classifier-node-save"));
    await waitFor(() =>
      expect(
        screen.getByTestId<HTMLTextAreaElement>("classifier-node-description").value,
      ).toContain("Черновик описания"),
    );
  });

  it("adds a child class and then deletes it", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");

    await user.click(screen.getByText("Добавить дочерний класс"));
    await user.type(screen.getByTestId("classifier-new-child-name"), "Новый класс");
    await user.click(screen.getByTestId("classifier-add-child"));

    // Название узла растянуто по нескольким вложенным <span> внутри
    // одной кнопки-строки — accessible name корректно учитывает их все.
    const newTreeNode = await screen.findByRole("button", { name: "Новый класс" });
    expect(newTreeNode).toBeInTheDocument();

    await user.click(newTreeNode);
    await screen.findByDisplayValue("Новый класс");
    await user.click(screen.getByTestId("classifier-node-delete"));

    // Удаление подтверждено (window.confirm застаблен на true) — узел
    // исчезает из дерева.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Новый класс" })).not.toBeInTheDocument(),
    );
  });

  it("saves an edited prompt directly (no separate template/override split) and can restore the default", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ClassifierLibraryStep />);
    await screen.findByTestId("classifier-node-panel");

    const promptField = screen.getByTestId("classifier-node-prompt");
    await user.clear(promptField);
    await user.type(promptField, "Кастомный промпт для корня");
    await user.click(screen.getByTestId("classifier-node-save-prompt"));

    await waitFor(() =>
      expect(screen.getByTestId("classifier-node-prompt")).toHaveValue(
        "Кастомный промпт для корня",
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("classifier-node-reset-prompt")).toBeEnabled(),
    );

    await user.click(screen.getByTestId("classifier-node-reset-prompt"));
    // После восстановления поле снова показывает непустой автосгенерированный
    // промпт — не остаётся пустым.
    await waitFor(() =>
      expect(
        screen.getByTestId<HTMLTextAreaElement>("classifier-node-prompt").value,
      ).toContain("АСУ"),
    );
  });
});
