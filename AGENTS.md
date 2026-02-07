## General

- Seguir el principio de S de SOLID
- Seguir estilos de implementación y/o testeo, esto incluye nombres, espaciado entre líneas y contextos  y en general las reglas del clean code
- NUNCA dejes comentarios
- Explicar claramente los cambios realizados en el chat
- Una vez hecho un cambio, sugerir actualización de sus tests (de existir)

## Testing

- Crear unit tests para los casos de uso. 
- Usa algún test ya creado como guía para la creación de nuevos tests
- Al crear variables para usar en los tests, unificar las que sean repetitivas para evitar su creacion en cada test. Si hay varias variables muy parecidas y cuya unificación tenga sentido, realizarla.
- Al crear variables/objetos de prueba usar la palabra "test" en strings semánticos (ej. name, description) para facilitar su identificación. EVITARLO en ids, fechas u otros identificadores técnicos; usar valores simples y reales cuando aplique. Por ejemplo: Habit.name = "testHabit". Ejemplo de uso incorrecto: Habit.date = "testDate" o Habit.id = "testId"
- Probar cada línea de código. 
    - Un solo test por flujo de ejecución:
    - Un test cuando una condición if se cumple.
    - Un test cuando no se cumple (incluyendo else o else if).
- Aplicar la misma lógica para estructuras anidadas.
- Mockear las funciones que no pertenezcan al caso de uso. 
- Nombrar los tests con el formato given..., then....
- Estructurar cada test en tres secciones:
    - Arrange: preparación del entorno y datos.
    - Action: ejecución del método bajo prueba.
    - Assert: verificación del resultado esperado. 
