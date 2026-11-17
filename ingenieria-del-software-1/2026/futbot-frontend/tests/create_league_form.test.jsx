import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CreateLeagueForm from "../src/components/create_league_form";
import { getMyPlayers, getMyBehaviors } from "../src/api/friendly";
import { createLeague } from "../src/api/leagues";
import { MemoryRouter } from "react-router-dom";

vi.mock("../src/api/friendly", () => ({
  getMyPlayers: vi.fn(),
  getMyBehaviors: vi.fn(),
}));
vi.mock("../src/api/leagues", () => ({ createLeague: vi.fn() }));


const PLAYER_NAMES = ["messi", "player0", "player1", "player2", "player3", "player4"];
const PLAYERS = PLAYER_NAMES.map((name) => ({ name }));
const BEHAVIORS = [
  { id: "1", name: "Ataque", is_preprogrammed: true },
  { id: "2", name: "Defensa", is_preprogrammed: true },
];

// Espera a que carguen las opciones y completa los 6 slots (jugador + comportamiento)
async function fill_squad(user) {
  await screen.findAllByRole("option", { name: /messi/ });
  const selects = screen.getAllByRole("combobox"); // 12: [jugador, comportamiento] x 6
  for (let i = 0; i < 6; i++) {
    await user.selectOptions(selects[i * 2], PLAYER_NAMES[i]);
    await user.selectOptions(selects[i * 2 + 1], "1");
  }
}

async function fill_fields(user) {
  await user.type(screen.getByLabelText("Nombre de la liga"), "Liga de prueba");
  await user.type(screen.getByLabelText("Mínimo de clubes"), "3");
  await user.type(screen.getByLabelText("Máximo de clubes"), "30");
  await user.type(screen.getByLabelText("Duración del partido"), "90");
}

const submit_button = () => screen.getByRole("button", { name: "Crear Liga" });

describe("CreateLeagueForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMyPlayers.mockResolvedValue(PLAYERS);
    getMyBehaviors.mockResolvedValue(BEHAVIORS);
    createLeague.mockResolvedValue({ code_to_join: "ABC123" });
  });

  it("deshabilita el botón con el plantel incompleto y lo habilita al completarlo", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()}/>
      </MemoryRouter>
    );

    expect(submit_button().disabled).toBe(true);

    await fill_squad(user);

    expect(submit_button().disabled).toBe(false);
  });

  it("muestra el campo contraseña solo si la liga es privada", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>  
    );

    expect(screen.queryByLabelText("Contraseña")).toBeNull();

    await user.click(screen.getByLabelText(/liga privada/i));

    expect(screen.getByLabelText("Contraseña")).not.toBeNull();
  });

  it("no llama a createLeague y muestra errores si los campos son inválidos", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>
    );

    await fill_squad(user);
    await user.click(submit_button());

    expect(await screen.findByText("El nombre es obligatorio")).not.toBeNull();
    expect(createLeague).not.toHaveBeenCalled();
  });

  it("envía la liga y muestra el código al recibir 201", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>
    );

    await fill_fields(user);
    await fill_squad(user);
    await user.click(submit_button());

    expect(await screen.findByText(/liga creada correctamente/i)).not.toBeNull();
    expect(screen.getByText("ABC123")).not.toBeNull();
    expect(screen.getByText("Compartí este código para que otros clubes se unan:")).not.toBeNull();

    expect(createLeague).toHaveBeenCalledTimes(1);
    const sent = createLeague.mock.calls[0][0];
    expect(sent.name).toBe("Liga de prueba");
    expect(sent.is_private).toBe(false);
    expect(sent.has_penalty_shootout).toBe(false);
    expect(sent.starters).toHaveLength(3);
    expect(sent.substitutes).toHaveLength(3);
    expect(sent.starters[0]).toEqual({ playerId: "messi", behaviorId: "1" });
  });

  it("envía has_penalty_shootout como true cuando se activa la definición por penales", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>
    );

    await fill_fields(user);
    await fill_squad(user);
    await user.click(screen.getByLabelText(/definición por penales/i));
    await user.click(submit_button());

    expect(await screen.findByText(/liga creada correctamente/i)).not.toBeNull();
    expect(createLeague.mock.calls[0][0].has_penalty_shootout).toBe(true);
  });

  it("pide compartir también la contraseña al crear una liga privada", async () => {
    createLeague.mockResolvedValue({ code_to_join: "ABC123", is_private: true });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>
    );

    await fill_fields(user);
    await user.click(screen.getByLabelText(/liga privada/i));
    await user.type(screen.getByLabelText("Contraseña"), "clave1234");
    await fill_squad(user);
    await user.click(submit_button());

    expect(
      await screen.findByText("Compartí este código y la contraseña para que otros clubes se unan:")
    ).not.toBeNull();
    expect(createLeague.mock.calls[0][0].password).toBe("clave1234");
  });

  it("muestra el error del backend y no muestra el éxito", async () => {
    createLeague.mockRejectedValue({ detail: "Ya existe una liga con ese nombre" });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CreateLeagueForm onCancel={vi.fn()} />
      </MemoryRouter>
    );

    await fill_fields(user);
    await fill_squad(user);
    await user.click(submit_button());

    expect(await screen.findByText("Ya existe una liga con ese nombre")).not.toBeNull();
    expect(screen.queryByText(/liga creada correctamente/i)).toBeNull();
  });
});