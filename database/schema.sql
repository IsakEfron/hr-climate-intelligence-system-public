SET FOREIGN_KEY_CHECKS = 0;

-- ─── PLANTAS ────────────────────────────────────────────────────
DROP TABLE IF EXISTS `plantas`;
CREATE TABLE `plantas` (
  `id_planta` INT NOT NULL AUTO_INCREMENT,
  `nombre`    VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id_planta`),
  UNIQUE KEY `uq_nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── ÁREAS ──────────────────────────────────────────────────────
DROP TABLE IF EXISTS `areas`;
CREATE TABLE `areas` (
  `id_area`   INT NOT NULL AUTO_INCREMENT,
  `nombre`    VARCHAR(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `id_planta` INT NOT NULL,
  PRIMARY KEY (`id_area`),
  KEY `fk_area_planta` (`id_planta`),
  CONSTRAINT `fk_area_planta`
    FOREIGN KEY (`id_planta`) REFERENCES `plantas` (`id_planta`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── ENCUESTAS ──────────────────────────────────────────────────
DROP TABLE IF EXISTS `encuestas`;
CREATE TABLE `encuestas` (
  `id_encuesta` INT NOT NULL AUTO_INCREMENT,
  `nombre`      VARCHAR(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fecha`       DATE DEFAULT NULL,
  PRIMARY KEY (`id_encuesta`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── EMPLEADOS — sin id_encuesta ────────────────────────────────
-- La relación empleado ↔ encuesta se obtiene via:
-- empleados → respuestas → preguntas → encuestas
DROP TABLE IF EXISTS `empleados`;
CREATE TABLE `empleados` (
  `id_empleado`      INT NOT NULL AUTO_INCREMENT,
  `nomina`           VARCHAR(50)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nombre`           VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `apellido_paterno` VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `apellido_materno` VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `genero`           VARCHAR(50)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `antiguedad`       VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `meses_antiguedad` INT DEFAULT NULL,
  `id_planta`        INT DEFAULT NULL,
  `id_area`          INT DEFAULT NULL,
  PRIMARY KEY (`id_empleado`),
  KEY `fk_emp_planta` (`id_planta`),
  KEY `fk_emp_area`   (`id_area`),
  KEY `idx_nomina`    (`nomina`),        -- búsquedas frecuentes por nómina
  CONSTRAINT `fk_emp_planta`
    FOREIGN KEY (`id_planta`) REFERENCES `plantas` (`id_planta`),
  CONSTRAINT `fk_emp_area`
    FOREIGN KEY (`id_area`)   REFERENCES `areas`   (`id_area`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── PREGUNTAS ──────────────────────────────────────────────────
DROP TABLE IF EXISTS `preguntas`;
CREATE TABLE `preguntas` (
  `id_pregunta` INT NOT NULL AUTO_INCREMENT,
  `id_encuesta` INT DEFAULT NULL,
  `numero`      DECIMAL(4,1) DEFAULT NULL,
  `texto`       TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `categoria`   VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo`        ENUM('escala','abierta') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id_pregunta`),
  KEY `fk_preg_encuesta` (`id_encuesta`),
  KEY `idx_categoria`    (`categoria`),  -- filtros por categoría en analítica
  CONSTRAINT `fk_preg_encuesta`
    FOREIGN KEY (`id_encuesta`) REFERENCES `encuestas` (`id_encuesta`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── RESPUESTAS ─────────────────────────────────────────────────
DROP TABLE IF EXISTS `respuestas`;
CREATE TABLE `respuestas` (
  `id_respuesta` INT NOT NULL AUTO_INCREMENT,
  `id_empleado`  INT DEFAULT NULL,
  `id_pregunta`  INT DEFAULT NULL,
  `valor`        INT DEFAULT NULL,
  `texto`        TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id_respuesta`),
  KEY `fk_resp_empleado`   (`id_empleado`),
  KEY `fk_resp_pregunta`   (`id_pregunta`),
  -- Este índice es crítico: el dashboard hace AVG(valor) agrupando
  -- por pregunta miles de veces. Sin él, full scan en cada consulta.
  KEY `idx_pregunta_valor` (`id_pregunta`, `valor`),
  CONSTRAINT `fk_resp_empleado`
    FOREIGN KEY (`id_empleado`) REFERENCES `empleados` (`id_empleado`) ON DELETE CASCADE,
  CONSTRAINT `fk_resp_pregunta`
    FOREIGN KEY (`id_pregunta`) REFERENCES `preguntas` (`id_pregunta`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── USUARIOS ───────────────────────────────────────────────────
DROP TABLE IF EXISTS `usuarios`;
CREATE TABLE `usuarios` (
  `id_usuario`      INT NOT NULL AUTO_INCREMENT,
  `username`        VARCHAR(50)  COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash`   VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nombre_completo` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rol`             VARCHAR(20)  COLLATE utf8mb4_unicode_ci DEFAULT 'consulta',
  `fecha_creacion`  TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_usuario`),
  UNIQUE KEY `uq_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── AUDITORÍA ──────────────────────────────────────────────────
DROP TABLE IF EXISTS `auditoria`;
CREATE TABLE `auditoria` (
  `id_log`    INT NOT NULL AUTO_INCREMENT,
  `usuario`   VARCHAR(50)  COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accion`    VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,  -- era 50, muy corto
  `detalle`   TEXT         COLLATE utf8mb4_unicode_ci,
  `fecha`     TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `ip_origen` VARCHAR(45)  COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id_log`),
  -- Índice compuesto: check_user_lockout() filtra por usuario+accion+fecha
  KEY `idx_usuario_accion_fecha` (`usuario`, `accion`, `fecha`),
  KEY `idx_fecha`                (`fecha`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── MANTENIMIENTO ──────────────────────────────────────────────
DROP TABLE IF EXISTS `mantenimiento`;
CREATE TABLE `mantenimiento` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `active`     TINYINT(1) DEFAULT 0,
  `start`      DATETIME DEFAULT NULL,
  `end`        DATETIME DEFAULT NULL,
  `notas`      TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_by` VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  -- Índice compuesto: is_maintenance_active() filtra por los tres campos
  KEY `idx_maint_activo` (`active`, `start`, `end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── POBLACIÓN ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `poblacion` (
  `id_poblacion`  INT NOT NULL AUTO_INCREMENT,
  `num_poblacion` INT NOT NULL DEFAULT 0,
  `id_encuesta`   INT NOT NULL,
  `id_planta`     INT NOT NULL,
  PRIMARY KEY (`id_poblacion`),
  UNIQUE KEY `uq_encuesta_planta` (`id_encuesta`, `id_planta`),
  KEY `fk_pob_encuesta` (`id_encuesta`),
  KEY `fk_pob_planta`   (`id_planta`),
  CONSTRAINT `fk_pob_encuesta`
    FOREIGN KEY (`id_encuesta`) REFERENCES `encuestas` (`id_encuesta`) ON DELETE CASCADE,
  CONSTRAINT `fk_pob_planta`
    FOREIGN KEY (`id_planta`)   REFERENCES `plantas`   (`id_planta`)  ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;