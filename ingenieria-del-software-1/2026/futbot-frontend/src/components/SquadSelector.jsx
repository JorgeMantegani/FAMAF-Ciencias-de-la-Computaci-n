import './SquadSelector.css'

export default function SquadSelector({ players, behaviors, squad, setSquad}) {

    // Obtiene los ids de los jugadores elegidos para evitar duplicados
    const getSelectedPlayersIds = () => {
        const starterIds = squad.starters.map((s) => String(s.playerId)).filter(Boolean);
        const substituteIds = squad.substitutes.map((s) => String(s.playerId)).filter(Boolean);
        return[...starterIds, ...substituteIds];
    };

    const handleSelectionChange = (type, index, field, value) => {
        const updatedList = squad[type].map((slot, i) => {
          if(i === index) {
            return { ...slot, [field]: value};
          }
          return slot;
        });

        setSquad({
           ...squad, 
           [type]: updatedList,
          });
    };

    const selectedIds = getSelectedPlayersIds();

    const renderSlot = (type, index, label) => {
        const currentSlot = squad[type][index] || { playerId: '', behaviorId: '' };

        return (
      <div key={`${type}-${index}`} className="slot-card">
        <h6 className="fw-bold">{label} {index + 1}</h6>
        <div className="row">
          {/* Selección de Jugador */}
          <div className="col">
            <select
              className="form-select"
              value={currentSlot.playerId}
              onChange={(e) => handleSelectionChange(type, index, 'playerId', e.target.value)}
            >
              <option value="">-- Seleccionar Jugador --</option>
              {players.map((p) => {
                const playerIdStr = String(p.id);
                const isSelectedElsewhere =
                  selectedIds.includes(playerIdStr) && playerIdStr !== String(currentSlot.playerId);

                return (
                  <option key={p.id} value={p.id} disabled={isSelectedElsewhere}>
                    {p.name} {isSelectedElsewhere ? '(Seleccionado)' : ''}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Selección de Comportamiento */}
          <div className="col">
            <select
              className="form-select"
              value={currentSlot.behaviorId}
              onChange={(e) => handleSelectionChange(type, index, 'behaviorId', e.target.value)}
            >
              <option value="">-- Seleccionar Estrategia --</option>
              {behaviors.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} {b.is_preprogrammed ? '(Preprogramado)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="squad-selector">
      <h5 className="text">Titulares (3 requeridos)</h5>
      {[0, 1, 2].map((i) => renderSlot('starters', i, 'Titular'))}

      <h5 className="text">Suplentes (3 requeridos)</h5>
      {[0, 1, 2].map((i) => renderSlot('substitutes', i, 'Suplente'))}
    </div>
  );
}
