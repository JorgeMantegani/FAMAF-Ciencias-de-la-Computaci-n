// Validacion de formulario de creacion de jugador
export function validate_player({
  name,
  power,
  agility,
  control,
  speed,
  strength
}) {
  const errors = {};

  name = name.trim();
  // Formato del nombre: no vacío, al menos 3 caracteres
  if (!name) {
    errors.name = 'El nombre es obligatorio';
  } else if (name.length < 3) {
    errors.name = 'El nombre debe tener al menos 3 caracteres';
  }

  const attributes = { power, agility, control, speed, strength };
  let sum = 0;
  let validAttributes = 0;

  const regex = /^\d+$/;// Solo digitos, al menos uno

  for (const [key, value] of Object.entries(attributes)) {
    // Campo vacío
    if (value.trim() === '') { //trim() para descartar espacios
      errors[key] = 'El campo es obligatorio';
      continue; 
    }

    // Formato segun regex
    if (!regex.test(value)) {
      errors[key] = 'Error de formato (ingrese un número entero)';
      continue;
    }

    const num = Number(value);

    // Cheueos de rango menor a 20 y mayor a 100
    if (num < 20) {
      errors[key] = 'Debe ser al menos 20';
      continue;
    }

    if (num > 100) {
      errors[key] = 'No puede ser mayor a 100';
      continue;
    }

    // Si llego aca, es valido
    sum += num;
    validAttributes++;
  }

  // Solo validar la suma cuando los 5 atributos son validos
  if (validAttributes === 5 && sum !== 300) {
    errors.sum = 'La suma de los atributos debe ser exactamente 300';
  }

  return {
    errors,
    sum: validAttributes === 5 ? sum : null
  };
}
