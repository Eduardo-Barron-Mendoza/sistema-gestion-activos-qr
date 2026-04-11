-- ==========================================
-- BASE DE DATOS: GestionActivos
-- ==========================================

CREATE DATABASE GestionActivos;
GO

USE GestionActivos;
GO

-- ==========================================
-- TABLA PERSONAS
-- ==========================================
CREATE TABLE Personas (
    idPersona INT IDENTITY(1,1) PRIMARY KEY,
    NombreCompleto VARCHAR(100) NOT NULL,
    Rol VARCHAR(50) NOT NULL,
    Puesto VARCHAR(50) NULL,
    Edad INT NULL,
    Domicilio VARCHAR(200) NULL,
    Foto NVARCHAR(255) NULL 
);
GO

-- ==========================================
-- TABLA USUARIOS
-- ==========================================
CREATE TABLE Usuarios (
    idUsuario INT IDENTITY(1,1) PRIMARY KEY,
    [User] VARCHAR(50) NOT NULL UNIQUE,
    Contra VARCHAR(255) NOT NULL,
    idPersona INT NOT NULL UNIQUE,
    FOREIGN KEY (idPersona) REFERENCES Personas(idPersona)
);
GO

-- ==========================================
-- TABLA EDIFICIOS
-- ==========================================
CREATE TABLE Edificios (
    idEdificio INT IDENTITY(1,1) PRIMARY KEY,
    Edificio VARCHAR(100) NOT NULL UNIQUE
);
GO

-- ==========================================
-- TABLA ACTIVOS
-- ==========================================
CREATE TABLE Activos (
    idActivo INT IDENTITY(1,1) PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    IdEdificio INT NULL,
    UbicacionActual VARCHAR(100) NULL,
    Garantia VARCHAR(50) NULL,
    FotoActivo VARCHAR(255) NULL,
    FechaEntrada DATE NOT NULL,
    HoraEntrada TIME NOT NULL,
    IdUsuario INT NOT NULL,
    QR VARCHAR(255) UNIQUE,
    FOREIGN KEY (IdUsuario) REFERENCES Usuarios(idUsuario),
    FOREIGN KEY (IdEdificio) REFERENCES Edificios(idEdificio)
);
GO

-- ==========================================
-- TABLA HISTORIAL
-- ==========================================
CREATE TABLE Historial (
    idHistorial INT IDENTITY(1,1) PRIMARY KEY,
    idUsuario INT NOT NULL,
    FechaEdicion DATE NOT NULL,
    HoraEdicion TIME NOT NULL,
    idActivo INT NOT NULL,
    Cambios VARCHAR(MAX) NOT NULL,
    FOREIGN KEY (idUsuario) REFERENCES Usuarios(idUsuario),
    FOREIGN KEY (idActivo) REFERENCES Activos(idActivo)
);
GO

-- ==========================================
-- TABLA DETALLE HISTORIAL
-- ==========================================
CREATE TABLE DetalleHistorial (
    idDH INT IDENTITY(1,1) PRIMARY KEY,
    idHistorial INT NOT NULL,
    CampoModificado VARCHAR(50) NOT NULL,
    ValorAnterior VARCHAR(MAX) NULL,
    ValorActual VARCHAR(MAX) NULL,
    FOREIGN KEY (idHistorial) REFERENCES Historial(idHistorial)
);
GO

-- ==========================================
-- DATOS DE PRUEBA
-- ==========================================

-- Personas
INSERT INTO Personas (NombreCompleto, Rol, Puesto, Edad, Domicilio, Foto)
VALUES 
('Ines', 'Administrador', 'Encargado TI', 22, 'Calle Falsa 123', null),
('Eduardo', 'Usuario', 'Recepción', 22, 'Av. Siempre Viva 456', null);

-- Usuarios
INSERT INTO Usuarios ([User], Contra, idPersona)
VALUES 
('ines', '123456', 1),
('eduardo', '123456', 2);

-- Edificios
INSERT INTO Edificios (Edificio)
VALUES 
('Edificio A'),
('Edificio B');

INSERT INTO Edificios (Edificio)
VALUES 
('Edificio C'),
('CIDEA'),
('CAPTA'),
('Biblioteca'),
('LT1');

select * from Usuarios
select * from Personas
select * from Edificios
select * from Activos
select * from Historial
select * from DetalleHistorial

ALTER TABLE Activos
DROP CONSTRAINT UQ__Activos__32152F1EF082B998;

CREATE UNIQUE INDEX UX_Activos_QR
ON Activos(QR)
WHERE QR IS NOT NULL;

--DELETE FROM DetalleHistorial;

--DBCC CHECKIDENT ('DetalleHistorial', RESEED, 0);

--DELETE FROM Historial;
--DBCC CHECKIDENT ('Historial', RESEED, 0);

-- 3️⃣ Vaciar Activos
--DELETE FROM Activos;
--DBCC CHECKIDENT ('Activos', RESEED, 0);
--
--DELETE FROM Usuarios;
--DBCC CHECKIDENT ('Usuarios', RESEED, 0);

--DELETE FROM Personas;
--DBCC CHECKIDENT ('Personas', RESEED, 0);

ALTER TABLE Activos
ADD Observaciones VARCHAR(MAX) NULL;

INSERT INTO Activos (Nombre, FechaEntrada, HoraEntrada, IdUsuario) 
VALUES ('Activo de Prueba', '2025-01-15', '10:30:00', 27)
