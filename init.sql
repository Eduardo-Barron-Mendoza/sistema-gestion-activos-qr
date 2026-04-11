-- ==========================================
-- BASE DE DATOS: GestionActivos (PostgreSQL)
-- ==========================================

-- TABLA PERSONAS
CREATE TABLE IF NOT EXISTS Personas (
    idPersona SERIAL PRIMARY KEY,
    NombreCompleto VARCHAR(100) NOT NULL,
    Rol VARCHAR(50) NOT NULL,
    Puesto VARCHAR(50) NULL,
    Edad INT NULL,
    Domicilio VARCHAR(200) NULL,
    Foto VARCHAR(255) NULL
);

-- TABLA USUARIOS
CREATE TABLE IF NOT EXISTS Usuarios (
    idUsuario SERIAL PRIMARY KEY,
    "User" VARCHAR(50) NOT NULL UNIQUE,
    Contra VARCHAR(255) NOT NULL,
    idPersona INT NOT NULL UNIQUE,
    FOREIGN KEY (idPersona) REFERENCES Personas(idPersona)
);

-- TABLA EDIFICIOS
CREATE TABLE IF NOT EXISTS Edificios (
    idEdificio SERIAL PRIMARY KEY,
    Edificio VARCHAR(100) NOT NULL UNIQUE
);

-- TABLA ACTIVOS
CREATE TABLE IF NOT EXISTS Activos (
    idActivo SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    IdEdificio INT NULL,
    UbicacionActual VARCHAR(100) NULL,
    Garantia VARCHAR(50) NULL,
    FotoActivo VARCHAR(255) NULL,
    FechaEntrada DATE NOT NULL,
    HoraEntrada TIME NOT NULL,
    IdUsuario INT NOT NULL,
    QR VARCHAR(255) NULL,
    Observaciones TEXT NULL,
    FOREIGN KEY (IdUsuario) REFERENCES Usuarios(idUsuario),
    FOREIGN KEY (IdEdificio) REFERENCES Edificios(idEdificio)
);

CREATE UNIQUE INDEX IF NOT EXISTS UX_Activos_QR ON Activos(QR) WHERE QR IS NOT NULL;

-- TABLA HISTORIAL
CREATE TABLE IF NOT EXISTS Historial (
    idHistorial SERIAL PRIMARY KEY,
    idUsuario INT NOT NULL,
    FechaEdicion DATE NOT NULL,
    HoraEdicion TIME NOT NULL,
    idActivo INT NOT NULL,
    Cambios TEXT NOT NULL,
    FOREIGN KEY (idUsuario) REFERENCES Usuarios(idUsuario),
    FOREIGN KEY (idActivo) REFERENCES Activos(idActivo)
);

-- TABLA DETALLE HISTORIAL
CREATE TABLE IF NOT EXISTS DetalleHistorial (
    idDH SERIAL PRIMARY KEY,
    idHistorial INT NOT NULL,
    CampoModificado VARCHAR(50) NOT NULL,
    ValorAnterior TEXT NULL,
    ValorActual TEXT NULL,
    FOREIGN KEY (idHistorial) REFERENCES Historial(idHistorial)
);

-- ==========================================
-- DATOS DE PRUEBA
-- ==========================================
INSERT INTO Personas (NombreCompleto, Rol, Puesto, Edad, Domicilio, Foto)
VALUES
('Ines', 'Administrador', 'Encargado TI', 22, 'Calle Falsa 123', null),
('Eduardo', 'Usuario', 'Recepción', 22, 'Av. Siempre Viva 456', null)
ON CONFLICT DO NOTHING;

INSERT INTO Usuarios ("User", Contra, idPersona)
VALUES
('ines', '123456', 1),
('eduardo', '123456', 2)
ON CONFLICT DO NOTHING;

INSERT INTO Edificios (Edificio)
VALUES
('Edificio A'), ('Edificio B'), ('Edificio C'),
('CIDEA'), ('CAPTA'), ('Biblioteca'), ('LT1')
ON CONFLICT DO NOTHING;
