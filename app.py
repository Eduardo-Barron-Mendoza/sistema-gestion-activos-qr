# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
import db  # tu archivo de conexión a la DB
import os
from werkzeug.utils import secure_filename
import qrcode
from datetime import datetime, timedelta
from flask_cors import CORS
import secrets
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import re
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "seguridad"

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORS(app)

UPLOAD_FOLDER = 'static/img_personas'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # crea carpeta si no existe

UPLOAD_ACTIVOS = 'static/img_activos'
os.makedirs(UPLOAD_ACTIVOS, exist_ok=True)

# =========================================
# LOGIN
# =========================================
@app.before_request
def csrf_protect():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)

    if request.method == "POST":
        token = session.get("csrf_token")
        form_token = request.form.get("csrf_token")
        if not token or token != form_token:
            abort(403)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("password")

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT u.idUsuario, u.Contra, p.Rol, p.NombreCompleto
            FROM Usuarios u
            JOIN Personas p ON u.idPersona = p.idPersona
            WHERE u."User" = %s
        """, (user,))

        row = cursor.fetchone()

        if row:
            user_id, pass_db, rol, nombre_completo = row

            if password == pass_db:
                session.clear()
                session["user_id"] = user_id
                session["rol"] = rol
                session["username"] = user
                session["nombre_completo"] = nombre_completo 

                # También guardar la foto de perfil en la sesión
                cursor.execute("SELECT Foto FROM Personas WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)", (user_id,))
                foto = cursor.fetchone()
                session["foto_perfil"] = foto[0] if foto else None

                if rol.lower() == "administrador":
                    return redirect(url_for("dashboard_admin"))
                else:
                    return redirect(url_for("dashboard_usuario"))
            else:
                flash("Contraseña incorrecta. Verifica tu usuario y contraseña.", "error")
                return redirect(url_for("login"))
        else:
            flash("Usuario no encontrado. Verifica tus credenciales.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

# =========================================
# DASHBOARD
# =========================================
@app.route("/dashboard_admin")
def dashboard_admin():
    # Primero verificar que el usuario está en sesión
    if "user_id" not in session:
        flash("Debes iniciar sesión", "danger")
        return redirect(url_for("login"))
    
    # Luego verificar que tiene rol de administrador
    if session.get("rol", "").lower() != "administrador":
        flash("No tienes permisos de administrador", "danger")
        return redirect(url_for("login"))
    
    # Ahora sí, asegurar que existe nombre_completo
    if 'nombre_completo' not in session:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT p.NombreCompleto 
            FROM Personas p 
            JOIN Usuarios u ON u.idPersona = p.idPersona 
            WHERE u.idUsuario = %s
        """, (session['user_id'],))
        nombre = cursor.fetchone()
        if nombre:
            session['nombre_completo'] = nombre[0]
        else:
            # Fallback: usar el username
            session['nombre_completo'] = session.get('username', 'Usuario')
    
    return render_template("dashboard_admin.html", username=session["username"])

@app.route("/dashboard_usuario")
def dashboard_usuario():
    if "user_id" not in session:
        flash("Debes iniciar sesión", "danger")
        return redirect(url_for("login"))
    
    # Asegurar que existe nombre_completo
    if 'nombre_completo' not in session:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT p.NombreCompleto 
            FROM Personas p 
            JOIN Usuarios u ON u.idPersona = p.idPersona 
            WHERE u.idUsuario = %s
        """, (session['user_id'],))
        nombre = cursor.fetchone()
        if nombre:
            session['nombre_completo'] = nombre[0]
        else:
            session['nombre_completo'] = session.get('username', 'Usuario')
    
    return render_template("dashboard_usuario.html", username=session["username"])

# =========================================
# CREAR USUARIO Y EDITAR USUARIO (ADMIN)
# =========================================
@app.route("/usuarios/crear", methods=["GET", "POST"])
def crear_usuario():
    if "user_id" not in session or session.get("rol", "").lower() != "administrador":
        flash("No tienes permisos", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        user = request.form["user"]
        password = request.form["password"]
        nombre = request.form["nombre"]
        rol = request.form["rol"]
        puesto = request.form["puesto"]
        edad = request.form["edad"]
        domicilio = request.form["domicilio"]

        # Guardar archivo de foto
        foto_file = request.files.get("foto")
        if foto_file and foto_file.filename != "":
            filename = secure_filename(foto_file.filename)
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            ruta_foto = ruta_foto.replace("\\", "/")  # normaliza la ruta
            foto_file.save(ruta_foto)
            foto_db = filename  # guardamos solo el nombre
        else:
            foto_db = None

        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO Personas (NombreCompleto, Rol, Puesto, Edad, Domicilio, Foto)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING idPersona
        """, (nombre, rol, puesto, edad, domicilio, foto_db,))
        id_persona = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO Usuarios ("User", Contra, idPersona)
            VALUES (%s, %s, %s)
        """, (user, password, id_persona,))
        db.conn.commit()

        # Después de guardar la foto y hacer commit
        if foto_db:
            session['foto_perfil'] = foto_db

        try:
                # Intentar enviar correo de bienvenida
                enviar_correo_bienvenida_func(user, nombre)
                flash("Usuario creado correctamente. Se envió un correo de bienvenida.", "success")
        except Exception as e:
                logger.error(f"Error al enviar correo de bienvenida: {e}")
                flash("Usuario creado correctamente, pero no se pudo enviar el correo de bienvenida.", "warning")
        return redirect(url_for("editar_usuario"))

    return render_template("crear_usuario.html")

@app.route("/usuarios/editar", methods=["GET", "POST"])
def editar_usuario():
    if "user_id" not in session or session.get("rol", "").lower() != "administrador":
        flash("No tienes permisos", "danger")
        return redirect(url_for("login"))

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT u.idUsuario, u."User", p.NombreCompleto, p.Rol, p.Puesto, p.Edad, p.Domicilio, p.Foto,
                   (SELECT COUNT(*) FROM Activos WHERE IdUsuario = u.idUsuario) as cantidad_activos
        FROM Usuarios u
        JOIN Personas p ON u.idPersona = p.idPersona
    """)
    usuarios = cursor.fetchall()

    if request.method == "POST":
        id_usuario = request.form["id_usuario"]
        nuevo_user = request.form.get("user")
        nuevo_nombre = request.form.get("nombre")
        nuevo_rol = request.form.get("rol")
        nuevo_puesto = request.form.get("puesto")
        nueva_edad = request.form.get("edad")
        nuevo_domicilio = request.form.get("domicilio")

        # Foto
        foto_file = request.files.get("foto")
        cursor.execute("SELECT p.Foto FROM Personas p JOIN Usuarios u ON u.idPersona=p.idPersona WHERE u.idUsuario = %s", id_usuario)
        foto_actual = cursor.fetchone()[0]

        if foto_file and foto_file.filename != "":
            filename = secure_filename(foto_file.filename)
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            foto_file.save(ruta_foto)
            foto_db = filename
        else:
            foto_db = foto_actual

        cursor.execute("""
            UPDATE Personas
            SET NombreCompleto = %s, Rol = %s, Puesto = %s, Edad = %s, Domicilio = %s, Foto = %s
            WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)
        """, (nuevo_nombre, nuevo_rol, nuevo_puesto, nueva_edad, nuevo_domicilio, foto_db, id_usuario,))

        cursor.execute("""
            UPDATE Usuarios
            SET "User" = %s
            WHERE idUsuario = %s
        """, (nuevo_user, id_usuario,))

        db.conn.commit()
        flash("Usuario actualizado", "success")
        return redirect(url_for("editar_usuario"))

    return render_template("editar_usuario.html", usuarios=usuarios)

# =========================================
# Eliminar usuarios
# =========================================
@app.route("/usuarios/eliminar/<int:id_usuario>", methods=["POST"])
def eliminar_usuario(id_usuario):

    if session.get("rol","").lower() != "administrador":
        abort(403)

    cursor = db.conn.cursor()
    
    # 1. Verificar que no sea el propio usuario
    if id_usuario == session.get('user_id'):
        flash("No puedes eliminar tu propia cuenta", "error")
        return redirect(url_for("editar_usuario"))
    
    try:
        # 2. Obtener idPersona
        cursor.execute("SELECT idPersona FROM Usuarios WHERE idUsuario = %s", (id_usuario,))
        resultado = cursor.fetchone()
        
        if not resultado:
            flash("Usuario no encontrado", "error")
            return redirect(url_for("editar_usuario"))
            
        id_persona = resultado[0]
        
        # 3. Obtener IDs de activos del usuario
        cursor.execute("SELECT idActivo FROM Activos WHERE IdUsuario = %s", (id_usuario,))
        activos = cursor.fetchall()
        
        # 4. Para cada activo, eliminar todo en orden
        for activo in activos:
            id_activo = activo[0]
            
            # Eliminar detalles del historial de este activo
            cursor.execute("DELETE FROM DetalleHistorial WHERE idHistorial IN (SELECT idHistorial FROM Historial WHERE idActivo = %s)", (id_activo,))
            
            # Eliminar historial de este activo
            cursor.execute("DELETE FROM Historial WHERE idActivo = %s", (id_activo,))
            
            # Eliminar el activo
            cursor.execute("DELETE FROM Activos WHERE idActivo = %s", (id_activo,))
        
        # 5. Eliminar historial donde el usuario es autor (de activos que no le pertenecen)
        cursor.execute("SELECT idHistorial FROM Historial WHERE idUsuario = %s", (id_usuario,))
        historiales = cursor.fetchall()
        
        for historial in historiales:
            id_historial = historial[0]
            cursor.execute("DELETE FROM DetalleHistorial WHERE idHistorial = %s", (id_historial,))
            cursor.execute("DELETE FROM Historial WHERE idHistorial = %s", (id_historial,))
        
        # 6. Eliminar usuario y persona
        cursor.execute("DELETE FROM Usuarios WHERE idUsuario = %s", (id_usuario,))
        cursor.execute("DELETE FROM Personas WHERE idPersona = %s", (id_persona,))
        
        db.conn.commit()
        flash("Usuario y todos sus registros asociados eliminados correctamente", "success")
        
    except Exception as e:
        db.conn.rollback()
        flash(f"Error al eliminar usuario: {str(e)}", "error")
    
    return redirect(url_for("editar_usuario"))

# =========================================
# API para llenar formulario al elegir usuario
# =========================================
@app.route("/usuarios/info/<int:id_usuario>")
def info_usuario(id_usuario):
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT u."User", p.NombreCompleto, p.Rol, p.Puesto, p.Edad, p.Domicilio, p.Foto
        FROM Usuarios u
        JOIN Personas p ON u.idPersona = p.idPersona
        WHERE u.idUsuario = %s
    """, (id_usuario,))
    row = cursor.fetchone()
    if row:
        data = {
            "user": row[0],
            "nombre": row[1],
            "rol": row[2],
            "puesto": row[3],
            "edad": row[4],
            "domicilio": row[5],
            "foto": f"/static/img_personas/{row[6]}" if row[6] else ""
        }
        return jsonify(data)
    return jsonify({})

# =========================================
# EDITAR PERFIL
# =========================================
@app.route("/perfil/editar", methods=["GET", "POST"])
def editar_perfil():
    if "user_id" not in session:
        flash("Debes iniciar sesión", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT u."User", p.NombreCompleto, p.Rol, p.Puesto, p.Edad, p.Domicilio, p.Foto
        FROM Usuarios u
        JOIN Personas p ON u.idPersona = p.idPersona
        WHERE u.idUsuario = %s
    """, (user_id,))
    usuario = cursor.fetchone()

    if request.method == "POST":
        nuevo_user = request.form["user"]
        nuevo_nombre = request.form["nombre"]
        nuevo_puesto = request.form["puesto"]
        nueva_edad = request.form["edad"]
        nuevo_domicilio = request.form["domicilio"]

        foto_file = request.files.get("foto")
        if foto_file and foto_file.filename != "":
            filename = secure_filename(foto_file.filename)
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            foto_file.save(ruta_foto)
            cursor.execute("""
                UPDATE Personas
                SET NombreCompleto = %s, Puesto = %s, Edad = %s, Domicilio = %s, Foto = %s
                WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)
            """, (nuevo_nombre, nuevo_puesto, nueva_edad, nuevo_domicilio, filename, user_id,))
            # Actualizar sesión con la nueva foto
            session["foto_perfil"] = filename
        else:
            cursor.execute("""
                UPDATE Personas
                SET NombreCompleto = %s, Puesto = %s, Edad = %s, Domicilio = %s
                WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)
            """, (nuevo_nombre, nuevo_puesto, nueva_edad, nuevo_domicilio, user_id,))

        cursor.execute("""
            UPDATE Usuarios
            SET "User" = %s
            WHERE idUsuario = %s
        """, (nuevo_user, user_id,))

        db.conn.commit()

        # ============================================
        # ACTUALIZAR LA SESIÓN CON LOS NUEVOS DATOS
        # ============================================
        session["username"] = nuevo_user
        session["nombre_completo"] = nuevo_nombre

        flash("Perfil actualizado correctamente", "success")
        return redirect(url_for("dashboard_admin" if session.get("rol") == "Administrador" else "dashboard_usuario"))

    return render_template("editar_perfil.html", usuario=usuario)

# =========================================
# REGISTRAR ACTIVO y HISTORIAL DE MOVIMIENTOS
# =========================================

@app.route('/registrar_activo', methods=['GET', 'POST'])
def registrar_activo():
    if 'rol' not in session or session['rol'].lower() != 'administrador':
        return redirect(url_for('login'))

    cursor = db.conn.cursor()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios")
    edificios = cursor.fetchall()

    if request.method == 'POST':
        nombre = request.form['nombre']
        id_edificio = request.form.get('id_edificio')
        ubicacion = request.form['ubicacion']
        garantia = request.form['garantia']
        id_usuario = session['user_id']
        observaciones = request.form['observaciones']

        ahora = datetime.now()
        fecha = ahora.date()
        hora = ahora.strftime("%H:%M:%S")

        # ============================================
        # MANEJO DE FOTO - Primero guardar temporal
        # ============================================
        foto_file = request.files.get('foto')
        foto_db = None
        foto_temporal = None
        
        if foto_file and foto_file.filename:
            # Guardar temporalmente con nombre seguro
            temp_filename = secure_filename(foto_file.filename)
            foto_temporal = os.path.join(UPLOAD_ACTIVOS, temp_filename)
            foto_file.save(foto_temporal)

        # INSERTAR ACTIVO
        cursor.execute("""
            INSERT INTO Activos
            (Nombre, IdEdificio, UbicacionActual, Garantia, FotoActivo,
             FechaEntrada, HoraEntrada, IdUsuario, Observaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING idActivo
        """, (nombre, id_edificio, ubicacion, garantia,
             None, fecha, hora, id_usuario, observaciones,))

        id_activo = cursor.fetchone()[0]

        # ============================================
        # AHORA SÍ, renombrar la foto con el ID del activo
        # ============================================
        if foto_temporal:
            # Obtener extensión del archivo original
            extension = os.path.splitext(foto_file.filename)[1]
            # Crear nombre definitivo con el ID del activo
            nombre_definitivo = f"activo_{id_activo}{extension}"
            ruta_definitiva = os.path.join(UPLOAD_ACTIVOS, nombre_definitivo)
            
            # Renombrar el archivo temporal
            import os as os_module
            os_module.rename(foto_temporal, ruta_definitiva)
            
            # Actualizar la base de datos con el nombre definitivo
            cursor.execute(
                "UPDATE Activos SET FotoActivo = %s WHERE idActivo = %s",
               (nombre_definitivo, id_activo)
            )
            foto_db = nombre_definitivo

        # GENERAR QR (URL)
        url_qr = f"https://qractivos.xyz/ver_activo/{id_activo}"
        nombre_qr = f"activo_{id_activo}.png"
        ruta_qr = generar_qr(url_qr, nombre_qr)

        # UPDATE QR
        cursor.execute(
            "UPDATE Activos SET QR = %s WHERE idActivo = %s",
           (ruta_qr, id_activo)
        )

        # ===============================
        # REGISTRAR EN HISTORIAL (ALTA)
        # ===============================

        cursor.execute("""
            INSERT INTO Historial
            (idUsuario, FechaEdicion, HoraEdicion, idActivo, Cambios)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING idHistorial
        """, (id_usuario, fecha, hora, id_activo, "Activo dado de alta",))

        id_historial = cursor.fetchone()[0]

        # DetalleHistorial (campos iniciales)
        campos = {
            "Nombre": nombre,
            "UbicacionActual": ubicacion,
            "Garantia": garantia,
            "FotoActivo": foto_db
        }

        for campo, valor in campos.items():
            cursor.execute("""
                INSERT INTO DetalleHistorial
                (idHistorial, CampoModificado, ValorAnterior, ValorActual)
                VALUES (%s, %s, %s, %s)
            """, (id_historial, campo, None, str(valor)))

        db.conn.commit()

        return render_template(
            "registrar_activo.html",
            edificios=edificios,
            activo_registrado=True,
            id_activo=id_activo,
            nombre=nombre,
            qr_path=f"activo_{id_activo}.png" 
        )
    
    # 👇 GET normal (NO existe id_activo aquí)
    return render_template('registrar_activo.html', edificios=edificios)

@app.route('/editar_activo', methods=['POST'])
def editar_activo():
    if 'user_id' not in session or session.get('rol', '').lower() != 'administrador':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    # Obtener datos del formulario
    id_activo = request.form.get('id_activo')
    nombre_nuevo = request.form.get('nombre')
    ubicacion_nueva = request.form.get('ubicacion')
    garantia_nueva = request.form.get('garantia')
    observaciones_nueva = request.form.get('observaciones')
    id_edificio = request.form.get('id_edificio')

    if not id_activo:
        flash('ID de activo no proporcionado', 'danger')
        return redirect(url_for('inventario_general'))

    cursor = db.conn.cursor()

    # Obtener datos actuales del activo
    cursor.execute("""
        SELECT Nombre, UbicacionActual, Garantia, FotoActivo, Observaciones, IdEdificio
        FROM Activos
        WHERE idActivo = %s
    """, (id_activo,))

    activo = cursor.fetchone()

    if not activo:
        flash('Activo no encontrado', 'danger')
        return redirect(url_for('inventario_general'))

    nombre_anterior, ubicacion_anterior, garantia_anterior, foto_anterior, observaciones_anterior, edificio_anterior = activo

    # Manejo de foto
    foto_nueva = foto_anterior
    archivo = request.files.get('foto')
    if archivo and archivo.filename:
        # Obtener extensión del archivo
        extension = os.path.splitext(archivo.filename)[1]
        # Nombre basado en el ID del activo
        filename = f"activo_{id_activo}{extension}"
        archivo.save(os.path.join(UPLOAD_ACTIVOS, filename))
        foto_nueva = filename

    # Actualizar activo
    cursor.execute("""
        UPDATE Activos
        SET Nombre = %s, UbicacionActual = %s, Garantia = %s, FotoActivo = %s, Observaciones = %s, IdEdificio = %s
        WHERE idActivo = %s
    """, (nombre_nuevo, ubicacion_nueva, garantia_nueva, foto_nueva, observaciones_nueva, id_edificio, id_activo,))

    ahora = datetime.now()
    fecha = ahora.date()
    hora = ahora.strftime("%H:%M:%S")
    id_usuario = session['user_id']

    # ===============================
    # REGISTRAR HISTORIAL (EDICIÓN)
    # ===============================

    cursor.execute("""
        INSERT INTO Historial
        (idUsuario, FechaEdicion, HoraEdicion, idActivo, Cambios)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING idHistorial
    """, (id_usuario, fecha, hora, id_activo, "Activo editado",))

    id_historial = cursor.fetchone()[0]

    # Comparar cambios
    cambios = [
        ("Nombre", nombre_anterior, nombre_nuevo),
        ("UbicacionActual", ubicacion_anterior, ubicacion_nueva),
        ("Garantia", garantia_anterior, garantia_nueva),
        ("FotoActivo", foto_anterior, foto_nueva),
        ("Observaciones", observaciones_anterior, observaciones_nueva),
        ("IdEdificio", edificio_anterior, id_edificio)
    ]

    for campo, anterior, nuevo in cambios:
        if str(anterior) != str(nuevo):
            cursor.execute("""
                INSERT INTO DetalleHistorial
                (idHistorial, CampoModificado, ValorAnterior, ValorActual)
                VALUES (%s, %s, %s, %s)
            """, (id_historial, campo, str(anterior), str(nuevo)))

    db.conn.commit()

    flash('Activo actualizado correctamente', 'success')
    return redirect(url_for('inventario_general'))

@app.route('/activos/eliminar/<int:id_activo>', methods=['POST'])
def eliminar_activo(id_activo):
    if 'user_id' not in session or session.get('rol', '').lower() != 'administrador':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    cursor = db.conn.cursor()
    
    try:
        # Primero eliminar detalles del historial
        cursor.execute("""
            DELETE FROM DetalleHistorial 
            WHERE idHistorial IN (SELECT idHistorial FROM Historial WHERE idActivo = %s)
        """, (id_activo,))
        
        # Luego eliminar historial
        cursor.execute("DELETE FROM Historial WHERE idActivo = %s", (id_activo,))
        
        # Finalmente eliminar activo
        cursor.execute("DELETE FROM Activos WHERE idActivo = %s", (id_activo,))
        
        db.conn.commit()
        flash('Activo eliminado correctamente', 'success')
    except Exception as e:
        db.conn.rollback()
        flash(f'Error al eliminar activo: {str(e)}', 'error')
    
    return redirect(url_for('inventario_general'))

@app.route('/historial_movimientos')
def historial_movimientos():

    if 'user_id' not in session or session.get('rol', '').lower() != 'administrador':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    cursor = db.conn.cursor()

    cursor.execute("""
        SELECT 
            h.idHistorial,
            p.NombreCompleto as nombre_usuario,
            a.Nombre as activo,
            h.FechaEdicion,
            h.HoraEdicion,
            h.Cambios
        FROM Historial h
        JOIN Usuarios u ON h.idUsuario = u.idUsuario
        JOIN Personas p ON u.idPersona = p.idPersona
        JOIN Activos a ON h.idActivo = a.idActivo
        ORDER BY h.FechaEdicion DESC, h.HoraEdicion DESC
        """)

    historial = cursor.fetchall()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios")
    edificios = cursor.fetchall()
    
    cursor.execute('''SELECT idUsuario, "User", NombreCompleto FROM Usuarios u JOIN Personas p ON u.idPersona = p.idPersona''')
    usuarios = cursor.fetchall()

    return render_template('historial_movimientos.html', historial=historial, edificios=edificios, usuarios=usuarios)

@app.route('/api/detalle_historial/<int:id_historial>')
def api_detalle_historial(id_historial):
    if 'user_id' not in session or session.get('rol', '').lower() != 'administrador':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    cursor = db.conn.cursor()

    # Obtener información general del historial
    cursor.execute("""
        SELECT h.FechaEdicion, h.HoraEdicion, p.NombreCompleto as Usuario
        FROM Historial h
        LEFT JOIN Usuarios u ON h.idUsuario = u.idUsuario
        LEFT JOIN Personas p ON u.idPersona = p.idPersona
        WHERE h.idHistorial = %s
    """, (id_historial,))
    
    historial = cursor.fetchone()
    
    # Obtener detalles
    cursor.execute("""
        SELECT CampoModificado, ValorAnterior, ValorActual
        FROM DetalleHistorial
        WHERE idHistorial = %s
        ORDER BY CampoModificado
        """, (id_historial,))
    
    detalles = cursor.fetchall()
    
    if not historial:
        return jsonify({'success': False, 'message': 'Historial no encontrado'}), 404
    
    return jsonify({
        'success': True,
        'id_historial': id_historial,
        'fecha': str(historial[0]) if historial and historial[0] else None,
        'hora': str(historial[1]) if historial and historial[1] else None,
        'usuario': historial[2] if historial else None,
        'detalles': [{
            'campo': d[0],
            'anterior': d[1],
            'actual': d[2]
        } for d in detalles]
    })

# =========================================
# GENERAR QR Y VER ACTIVO
# =========================================

def generar_qr(texto, nombre_archivo):
    ruta = f"static/qr_activos/{nombre_archivo}"
    os.makedirs("static/qr_activos", exist_ok=True)

    img = qrcode.make(texto)
    img.save(ruta)

    return ruta

@app.route('/ver_activo/<int:id_activo>')
def ver_activo(id_activo):
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT Nombre, UbicacionActual, Garantia, FechaEntrada, HoraEntrada, FotoActivo, QR, Observaciones
        FROM Activos
        WHERE idActivo = %s
    """, (id_activo,))

    activo = cursor.fetchone()

    if not activo:
        return "Activo no encontrado", 404
    
    # 🔥 Obtener historial SOLO de este activo
    cursor.execute("""
        SELECT 
            H.idHistorial,
            U."User",
            H.FechaEdicion,
            H.HoraEdicion,
            H.Cambios
        FROM Historial H
        JOIN Usuarios U ON H.idUsuario = U.idUsuario
        WHERE H.idActivo = %s
        ORDER BY H.idHistorial DESC
            LIMIT 1    """, (id_activo,))

    historial = cursor.fetchall()

    return render_template("ver_activo.html", activo=activo, historial=historial)

# =========================================
# INVENTARIO GENERAL
# =========================================

@app.route('/inventario_general')
def inventario_general():
    if 'rol' not in session or session['rol'].lower() != 'administrador':
        return redirect(url_for('login'))

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT 
            a.idActivo,
            a.Nombre,
            e.Edificio,
            a.UbicacionActual,
            a.Garantia,
            a.FechaEntrada,
            a.FotoActivo,
            a.QR,
            a.Observaciones,
            a.IdEdificio 
        FROM Activos a
        LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
        ORDER BY a.idActivo DESC
        """)
    activos = cursor.fetchall()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios ORDER BY Edificio")
    edificios = cursor.fetchall()

    return render_template(
        'inventario_general.html',
        activos=activos,
        edificios=edificios
    )

# =========================================
# LOGOUT
# =========================================
@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))

# =========================================
# API Y SUS CONSUMOS (EJEMPLO PARA ACTIVOS)
# =========================================
@app.route("/api/activos", methods=["GET"])
def api_activos():
    cursor = db.conn.cursor()
    cursor.execute("SELECT idActivo, Nombre, UbicacionActual FROM Activos")
    rows = cursor.fetchall()

    activos = []
    for r in rows:
        activos.append({
            "id": r[0],
            "nombre": r[1],
            "ubicacion": r[2]
        })

    return jsonify(activos)

@app.route('/api/buscar_activo')
def api_buscar_activo():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'success': False, 'message': 'Ingresa un término de búsqueda'})
    
    cursor = db.conn.cursor()
    
    # Buscar por ID o por nombre
    try:
        # Intentar buscar por ID si es número
        if query.isdigit():
            cursor.execute("""
                SELECT a.idActivo, a.Nombre, e.Edificio, a.UbicacionActual, 
                       a.Garantia, a.FechaEntrada, a.FotoActivo, a.QR, a.Observaciones,
                       u."User" as Usuario
                FROM Activos a
                LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
                LEFT JOIN Usuarios u ON a.IdUsuario = u.idUsuario
                WHERE a.idActivo = %s
            """, (int(query,)))
        else:
            # Buscar por nombre parcial
            cursor.execute("""
                SELECT a.idActivo, a.Nombre, e.Edificio, a.UbicacionActual, 
                       a.Garantia, a.FechaEntrada, a.FotoActivo, a.QR, a.Observaciones,
                       u."User" as Usuario
                FROM Activos a
                LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
                LEFT JOIN Usuarios u ON a.IdUsuario = u.idUsuario
                WHERE a.Nombre LIKE %s OR a.QR LIKE %s
            """, (f'%{query}%', f'%{query}%',))
        
        activo = cursor.fetchone()
        
        if activo:
            return jsonify({
                'success': True,
                'activo': {
                    'id': activo[0],
                    'nombre': activo[1],
                    'edificio': activo[2],
                    'ubicacion': activo[3],
                    'garantia': activo[4],
                    'fecha': str(activo[5]) if activo[5] else None,
                    'foto': activo[6],
                    'qr': activo[7],
                    'observaciones': activo[8],
                    'usuario': activo[9]
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Activo no encontrado'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/activos_recientes')
def api_activos_recientes():
    limite = request.args.get('limite', 5, type=int)
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT 
            a.idActivo, 
            a.Nombre, 
            e.Edificio, 
            a.UbicacionActual,
            a.Garantia,
            a.FechaEntrada,
            a.FotoActivo,
            a.QR,
            a.Observaciones,
            u."User" as Usuario
        FROM Activos a
        LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
        LEFT JOIN Usuarios u ON a.IdUsuario = u.idUsuario
        ORDER BY a.FechaEntrada DESC
        """, (limite,))
    
    activos = cursor.fetchall()
    
    return jsonify({
        'success': True,
        'activos': [{
            'id': a[0],
            'nombre': a[1],
            'edificio': a[2],
            'ubicacion': a[3],
            'garantia': a[4],
            'fecha': str(a[5]) if a[5] else None,
            'foto': a[6],
            'qr': a[7],
            'observaciones': a[8],
            'usuario': a[9]
        } for a in activos]
    })

@app.route('/escanear_activo')
def escanear_activo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('escanear.html')

@app.route('/api/buscar_sugerencias')
def api_buscar_sugerencias():
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'success': False, 'resultados': []})
    
    cursor = db.conn.cursor()
    
    # Buscar activos que coincidan con el nombre o ID
    cursor.execute("""
        SELECT 
            a.idActivo,
            a.Nombre,
            e.Edificio,
            a.UbicacionActual
        FROM Activos a
        LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
        WHERE a.Nombre LIKE %s OR a.idActivo::TEXT LIKE %s
        ORDER BY 
            CASE 
                WHEN a.Nombre LIKE %s THEN 1
                WHEN a.Nombre LIKE %s THEN 2
                ELSE 3
            END,
            a.Nombre
        LIMIT 10
    """, (f'%{query}%', f'%{query}%', f'{query}%', f'% {query}%',))
    
    resultados = cursor.fetchall()
    
    return jsonify({
        'success': True,
        'resultados': [{
            'id': r[0],
            'nombre': r[1],
            'edificio': r[2],
            'ubicacion': r[3]
        } for r in resultados]
    })
# =========================================
# USUARIOS REGISTRAR ACTIVOS
# =========================================
@app.route('/registrar_activo/usuario', methods=['GET', 'POST'])
def registrar_activo_usuario():
    if 'rol' not in session or session['rol'].lower() != 'usuario':
        return redirect(url_for('login'))

    cursor = db.conn.cursor()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios")
    edificios = cursor.fetchall()

    if request.method == 'POST':
        nombre = request.form['nombre']
        id_edificio = request.form.get('id_edificio')
        ubicacion = request.form['ubicacion']
        garantia = request.form['garantia']
        id_usuario = session['user_id']
        observaciones = request.form['observaciones']

        ahora = datetime.now()
        fecha = ahora.date()
        hora = ahora.strftime("%H:%M:%S")

        # ============================================
        # MANEJO DE FOTO - Primero guardar temporal
        # ============================================
        foto_file = request.files.get('foto')
        foto_db = None
        foto_temporal = None
        
        if foto_file and foto_file.filename:
            # Guardar temporalmente con nombre seguro
            temp_filename = secure_filename(foto_file.filename)
            foto_temporal = os.path.join(UPLOAD_ACTIVOS, temp_filename)
            foto_file.save(foto_temporal)

        # INSERTAR ACTIVO
        cursor.execute("""
            INSERT INTO Activos
            (Nombre, IdEdificio, UbicacionActual, Garantia, FotoActivo,
             FechaEntrada, HoraEntrada, IdUsuario, Observaciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING idActivo
        """, (nombre, id_edificio, ubicacion, garantia,
             None, fecha, hora, id_usuario, observaciones,))

        id_activo = cursor.fetchone()[0]

        # ============================================
        # AHORA SÍ, renombrar la foto con el ID del activo
        # ============================================
        if foto_temporal:
            # Obtener extensión del archivo original
            extension = os.path.splitext(foto_file.filename)[1]
            # Crear nombre definitivo con el ID del activo
            nombre_definitivo = f"activo_{id_activo}{extension}"
            ruta_definitiva = os.path.join(UPLOAD_ACTIVOS, nombre_definitivo)
            
            # Renombrar el archivo temporal
            import os as os_module
            os_module.rename(foto_temporal, ruta_definitiva)
            
            # Actualizar la base de datos con el nombre definitivo
            cursor.execute(
                "UPDATE Activos SET FotoActivo = %s WHERE idActivo = %s",
               (nombre_definitivo, id_activo)
            )
            foto_db = nombre_definitivo

        # GENERAR QR (URL)
        url_qr = f"https://qractivos.xyz/ver_activo/{id_activo}"
        nombre_qr = f"activo_{id_activo}.png"
        ruta_qr = generar_qr(url_qr, nombre_qr)

        # UPDATE QR
        cursor.execute(
            "UPDATE Activos SET QR = %s WHERE idActivo = %s",
           (ruta_qr, id_activo)
        )

        # ===============================
        # REGISTRAR EN HISTORIAL (ALTA)
        # ===============================

        cursor.execute("""
            INSERT INTO Historial
            (idUsuario, FechaEdicion, HoraEdicion, idActivo, Cambios)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING idHistorial
        """, (id_usuario, fecha, hora, id_activo, "Activo dado de alta",))

        id_historial = cursor.fetchone()[0]

        # DetalleHistorial (campos iniciales)
        campos = {
            "Nombre": nombre,
            "UbicacionActual": ubicacion,
            "Garantia": garantia,
            "FotoActivo": foto_db
        }

        for campo, valor in campos.items():
            cursor.execute("""
                INSERT INTO DetalleHistorial
                (idHistorial, CampoModificado, ValorAnterior, ValorActual)
                VALUES (%s, %s, %s, %s)
            """, (id_historial, campo, None, str(valor)))

        db.conn.commit()

        return render_template(
            "registrar_activo_usuario.html",
            edificios=edificios,
            activo_registrado=True,
            id_activo=id_activo,
            nombre=nombre,
            qr_path=f"activo_{id_activo}.png" 
        )
    
    # 👇 GET normal (NO existe id_activo aquí)
    return render_template('registrar_activo_usuario.html', edificios=edificios)

# =========================================
# INVENTARIO GENERAL DEL USUARIO
# =========================================

@app.route('/inventario_general/usuario')
def inventario_general_usuario():
    if 'rol' not in session or session['rol'].lower() != 'usuario':
        return redirect(url_for('login'))

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT 
            a.idActivo,
            a.Nombre,
            e.Edificio,
            a.UbicacionActual,
            a.Garantia,
            a.FechaEntrada,
            a.FotoActivo,
            a.QR,
            a.Observaciones,
            a.IdEdificio 
        FROM Activos a
        LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
        ORDER BY a.FechaEntrada DESC
        """)
    activos = cursor.fetchall()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios ORDER BY Edificio")
    edificios = cursor.fetchall()

    return render_template(
        'inventario_general_usuario.html',
        activos=activos,
        edificios=edificios
    )

@app.route('/editar_activo/usuario', methods=['GET', 'POST'])
def editar_activo_usuario():
    if 'user_id' not in session or session.get('rol', '').lower() != 'usuario':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    # Obtener datos del formulario
    id_activo = request.form.get('id_activo')
    nombre_nuevo = request.form.get('nombre')
    ubicacion_nueva = request.form.get('ubicacion')
    garantia_nueva = request.form.get('garantia')
    observaciones_nueva = request.form.get('observaciones')
    id_edificio = request.form.get('id_edificio')

    if not id_activo:
        flash('ID de activo no proporcionado', 'danger')
        return redirect(url_for('inventario_general_usuario'))

    cursor = db.conn.cursor()

    # Obtener datos actuales del activo
    cursor.execute("""
        SELECT Nombre, UbicacionActual, Garantia, FotoActivo, Observaciones, IdEdificio
        FROM Activos
        WHERE idActivo = %s
    """, (id_activo,))

    activo = cursor.fetchone()

    if not activo:
        flash('Activo no encontrado', 'danger')
        return redirect(url_for('inventario_general_usuario'))

    nombre_anterior, ubicacion_anterior, garantia_anterior, foto_anterior, observaciones_anterior, edificio_anterior = activo

    # Manejo de foto
    foto_nueva = foto_anterior
    archivo = request.files.get('foto')
    if archivo and archivo.filename:
        # Obtener extensión del archivo
        extension = os.path.splitext(archivo.filename)[1]
        # Nombre basado en el ID del activo
        filename = f"activo_{id_activo}{extension}"
        archivo.save(os.path.join(UPLOAD_ACTIVOS, filename))
        foto_nueva = filename

    # Actualizar activo
    cursor.execute("""
        UPDATE Activos
        SET Nombre = %s, UbicacionActual = %s, Garantia = %s, FotoActivo = %s, Observaciones = %s, IdEdificio = %s
        WHERE idActivo = %s
    """, (nombre_nuevo, ubicacion_nueva, garantia_nueva, foto_nueva, observaciones_nueva, id_edificio, id_activo,))

    ahora = datetime.now()
    fecha = ahora.date()
    hora = ahora.strftime("%H:%M:%S")
    id_usuario = session['user_id']

    # ===============================
    # REGISTRAR HISTORIAL (EDICIÓN)
    # ===============================

    cursor.execute("""
        INSERT INTO Historial
        (idUsuario, FechaEdicion, HoraEdicion, idActivo, Cambios)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING idHistorial
    """, (id_usuario, fecha, hora, id_activo, "Activo editado",))

    id_historial = cursor.fetchone()[0]

    # Comparar cambios
    cambios = [
        ("Nombre", nombre_anterior, nombre_nuevo),
        ("UbicacionActual", ubicacion_anterior, ubicacion_nueva),
        ("Garantia", garantia_anterior, garantia_nueva),
        ("FotoActivo", foto_anterior, foto_nueva),
        ("Observaciones", observaciones_anterior, observaciones_nueva),
        ("IdEdificio", edificio_anterior, id_edificio)
    ]

    for campo, anterior, nuevo in cambios:
        if str(anterior) != str(nuevo):
            cursor.execute("""
                INSERT INTO DetalleHistorial
                (idHistorial, CampoModificado, ValorAnterior, ValorActual)
                VALUES (%s, %s, %s, %s)
            """, (id_historial, campo, str(anterior), str(nuevo)))

    db.conn.commit()

    flash('Activo actualizado correctamente', 'success')
    return redirect(url_for('inventario_general_usuario'))

@app.route('/historial_movimientos/usuario')
def historial_movimientos_usuario():

    if 'user_id' not in session or session.get('rol', '').lower() != 'usuario':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    cursor = db.conn.cursor()

    cursor.execute("""
        SELECT 
            h.idHistorial,
            p.NombreCompleto as nombre_usuario,
            a.Nombre as activo,
            h.FechaEdicion,
            h.HoraEdicion,
            h.Cambios
        FROM Historial h
        JOIN Usuarios u ON h.idUsuario = u.idUsuario
        JOIN Personas p ON u.idPersona = p.idPersona
        JOIN Activos a ON h.idActivo = a.idActivo
        ORDER BY h.FechaEdicion DESC, h.HoraEdicion DESC
        """)

    historial = cursor.fetchall()

    cursor.execute("SELECT idEdificio, Edificio FROM Edificios")
    edificios = cursor.fetchall()
    
    cursor.execute('''SELECT idUsuario, "User", NombreCompleto FROM Usuarios u JOIN Personas p ON u.idPersona = p.idPersona''')
    usuarios = cursor.fetchall()

    return render_template('historial_movimientos_usuario.html', historial=historial, edificios=edificios, usuarios=usuarios)

@app.route('/api/detalle_historial/<int:id_historial>/usuario')
def api_detalle_historial_usuario(id_historial):
    if 'user_id' not in session or session.get('rol', '').lower() != 'usuario':
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    cursor = db.conn.cursor()

    # Obtener información general del historial
    cursor.execute("""
        SELECT h.FechaEdicion, h.HoraEdicion, p.NombreCompleto as Usuario
        FROM Historial h
        LEFT JOIN Usuarios u ON h.idUsuario = u.idUsuario
        LEFT JOIN Personas p ON u.idPersona = p.idPersona
        WHERE h.idHistorial = %s
    """, (id_historial,))
    
    historial = cursor.fetchone()
    
    # Obtener detalles
    cursor.execute("""
        SELECT CampoModificado, ValorAnterior, ValorActual
        FROM DetalleHistorial
        WHERE idHistorial = %s
        ORDER BY CampoModificado
        """, (id_historial,))
    
    detalles = cursor.fetchall()
    
    if not historial:
        return jsonify({'success': False, 'message': 'Historial no encontrado'}), 404
    
    return jsonify({
        'success': True,
        'id_historial': id_historial,
        'fecha': str(historial[0]) if historial and historial[0] else None,
        'hora': str(historial[1]) if historial and historial[1] else None,
        'usuario': historial[2] if historial else None,
        'detalles': [{
            'campo': d[0],
            'anterior': d[1],
            'actual': d[2]
        } for d in detalles]
    })

@app.route("/perfil/editar/usuario", methods=["GET", "POST"])
def editar_perfil_usuario():
    if "user_id" not in session:
        flash("Debes iniciar sesión", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT u."User", p.NombreCompleto, p.Rol, p.Puesto, p.Edad, p.Domicilio, p.Foto
        FROM Usuarios u
        JOIN Personas p ON u.idPersona = p.idPersona
        WHERE u.idUsuario = %s
    """, (user_id,))
    usuario = cursor.fetchone()

    if request.method == "POST":
        nuevo_user = request.form["user"]
        nuevo_nombre = request.form["nombre"]
        nuevo_puesto = request.form["puesto"]
        nueva_edad = request.form["edad"]
        nuevo_domicilio = request.form["domicilio"]

        foto_file = request.files.get("foto")
        if foto_file and foto_file.filename != "":
            filename = secure_filename(foto_file.filename)
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename).replace("\\", "/")
            foto_file.save(ruta_foto)
            cursor.execute("""
                UPDATE Personas
                SET NombreCompleto = %s, Puesto = %s, Edad = %s, Domicilio = %s, Foto = %s
                WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)
            """, (nuevo_nombre, nuevo_puesto, nueva_edad, nuevo_domicilio, filename, user_id,))
        else:
            cursor.execute("""
                UPDATE Personas
                SET NombreCompleto = %s, Puesto = %s, Edad = %s, Domicilio = %s
                WHERE idPersona = (SELECT idPersona FROM Usuarios WHERE idUsuario = %s)
            """, (nuevo_nombre, nuevo_puesto, nueva_edad, nuevo_domicilio, user_id,))

        cursor.execute("""
            UPDATE Usuarios
            SET "User" = %s
            WHERE idUsuario = %s
        """, (nuevo_user, user_id,))

        db.conn.commit()
        flash("Perfil actualizado correctamente", "success")
        return redirect(url_for("dashboard_usuario" if session.get("rol") == "usuario" else "dashboard_usuario"))

    return render_template("editar_perfil_usuario.html", usuario=usuario)

@app.route('/activos/eliminar/<int:id_activo>/usuario', methods=['POST'])
def eliminar_activo_usuario(id_activo):
    if 'user_id' not in session or session.get('rol', '').lower() != 'usuario':
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))

    cursor = db.conn.cursor()
    
    try:
        # Primero eliminar detalles del historial
        cursor.execute("""
            DELETE FROM DetalleHistorial 
            WHERE idHistorial IN (SELECT idHistorial FROM Historial WHERE idActivo = %s)
        """, (id_activo,))
        
        # Luego eliminar historial
        cursor.execute("DELETE FROM Historial WHERE idActivo = %s", (id_activo,))
        
        # Finalmente eliminar activo
        cursor.execute("DELETE FROM Activos WHERE idActivo = %s", (id_activo,))
        
        db.conn.commit()
        flash('Activo eliminado correctamente', 'success')
    except Exception as e:
        db.conn.rollback()
        flash(f'Error al eliminar activo: {str(e)}', 'error')
    
    return redirect(url_for('inventario_general_usuario'))

# =========================================
# CORREO DE BIENVENIDA (EJEMPLO DE API)
# =========================================
def enviar_correo_bienvenida_func(email, nombre):
    """
    Función auxiliar para enviar correo de bienvenida
    """
    remitente = os.environ.get('MAIL_USERNAME')
    password = os.environ.get('MAIL_PASSWORD')
    
    if not remitente or not password:
        logger.error("Credenciales de correo no configuradas")
        return False
    
    # Crear mensaje
    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = email
    msg['Subject'] = "🎉 ¡Bienvenido al Sistema SGAFAQ!"
    
    # Cuerpo del correo
    cuerpo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #00c97a 0%, #009e5e 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: #00c97a;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin:0;">SGAFAQ</h1>
                <p style="margin:5px 0 0; opacity:0.9;">Sistema de Gestión de Activos Fijos</p>
            </div>
            <div class="content">
                <h2 style="color: #00c97a; margin-top:0;">¡Bienvenido al sistema!</h2>
                <p>Hola <strong>{nombre}</strong>,</p>
                <p>Tu cuenta ha sido creada exitosamente en el Sistema de Gestión de Activos Fijos.</p>
                
                <div style="background:#e8f5e9; padding:15px; border-radius:5px; margin:20px 0;">
                    <h3 style="color:#00c97a; margin-top:0;">✅ Tu cuenta está activa</h3>
                    <p>Ya puedes acceder al sistema con tus credenciales:</p>
                    <ul style="list-style-type:none; padding:0;">
                        <li>🌐 <strong>URL de acceso:</strong> <a href="https://qractivos.xyz" style="color:#00c97a;">https://qractivos.xyz</a></li>
                        <li>👤 <strong>Usuario:</strong> {email}</li>
                    </ul>
                </div>
                
                <h3>¿Qué puedes hacer ahora?</h3>
                <ul>
                    <li>📊 Explorar el dashboard principal</li>
                    <li>📦 Registrar nuevos activos</li>
                    <li>🔍 Escanear códigos QR</li>
                    <li>📜 Ver historial de movimientos</li>
                </ul>
                
                <p style="text-align:center;">
                    <a href="https://qractivos.xyz" class="button">Acceder al sistema</a>
                </p>
            </div>
            <div class="footer">
                <p>Este es un correo automático, por favor no responder.</p>
                <p>&copy; 2025 SGAFAQ - Todos los derechos reservados</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(cuerpo, 'html'))
    
    # Enviar correo
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(remitente, password)
    server.send_message(msg)
    server.quit()
    
    logger.info(f"✅ Correo de bienvenida enviado a {email}")
    return True

@app.route('/api/enviar_correo_bienvenida', methods=['POST'])
def enviar_correo_bienvenida():
    data = request.json
    email = data.get('email')
    nombre = data.get('nombre')
    
    try:
        enviar_correo_bienvenida_func(email, nombre)
        return jsonify({'success': True, 'message': 'Correo enviado'})
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# =========================================
# GRAFICAS
# =========================================

@app.route('/api/dashboard_stats')
def dashboard_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Activos")
        total_activos = cursor.fetchone()[0]
        
        # IMPORTANTE: Crear un NUEVO cursor para cada consulta
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        total_usuarios = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Historial")
        total_movimientos = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Activos WHERE Garantia IS NOT NULL AND Garantia != ''")
        total_garantias = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Personas WHERE Rol = 'Administrador'")
        total_admins = cursor.fetchone()[0]

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT Nombre, FechaEntrada
            FROM Activos
            ORDER BY FechaEntrada ASC, HoraEntrada ASC
            LIMIT 1        """)
        mas_antiguo = cursor.fetchone()
        
        activo_mas_antiguo = mas_antiguo[0] if mas_antiguo else 'Ninguno'
        fecha_mas_antigua = mas_antiguo[1].strftime('%Y-%m-%d') if mas_antiguo and mas_antiguo[1] else ''
        
        print(f"✅ Activo más antiguo: {activo_mas_antiguo}")
        print(f"✅ Fecha más antigua: {fecha_mas_antigua}")
        
        return jsonify({
            'activos': total_activos,
            'usuarios': total_usuarios,
            'movimientos': total_movimientos,
            'garantias': total_garantias,
            'administradores': total_admins,
            'activo_mas_antiguo': activo_mas_antiguo,
            'fecha_mas_antigua': fecha_mas_antigua
        })
        
    except Exception as e:
        print(f"Error en dashboard_stats: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/usuarios_stats')
def usuarios_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        total_usuarios = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Personas WHERE Rol = 'Administrador'")
        total_admins = cursor.fetchone()[0]
        
        total_usuarios_normales = total_usuarios - total_admins
        
        return jsonify({
            'total': total_usuarios,
            'administradores': total_admins,
            'usuarios': total_usuarios_normales
        })
        
    except Exception as e:
        print(f"Error en usuarios_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/activos_por_fecha')
def activos_por_fecha():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    edificio_id = request.args.get('edificio_id', 'todos')
    cursor = db.conn.cursor()
    
    try:
        # Construir filtro de edificio
        filtro_edificio = ""
        params = []
        if edificio_id and edificio_id != 'todos':
            filtro_edificio = "AND a.IdEdificio = %s"
            params.append(edificio_id)
        
        # Query para agrupar por períodos de 10 días
        query = f"""
            SELECT 
                ('2000-01-01'::date + (((a.FechaEntrada - '2000-01-01'::date) / 10) * 10) * INTERVAL '1 day') as periodo_inicio,
                COUNT(*) as cantidad
            FROM Activos a
            WHERE a.FechaEntrada >= NOW() - INTERVAL '90 days'
            {filtro_edificio}
            GROUP BY (a.FechaEntrada - '2000-01-01'::date) / 10
            ORDER BY periodo_inicio
        """
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        periodos = []
        cantidades = []
        
        for r in resultados:
            # ✅ timedelta AHORA SÍ ESTÁ DEFINIDO
            fecha_inicio = r[0].strftime('%Y-%m-%d')
            fecha_fin = (r[0] + timedelta(days=9)).strftime('%Y-%m-%d')
            periodos.append(f"{fecha_inicio} al {fecha_fin}")
            cantidades.append(r[1])
        
        # Obtener lista de edificios para el filtro
        cursor.execute("SELECT idEdificio, Edificio FROM Edificios ORDER BY Edificio")
        edificios = cursor.fetchall()
        
        return jsonify({
            'periodos': periodos,
            'cantidades': cantidades,
            'edificios': [{'id': e[0], 'nombre': e[1]} for e in edificios]
        })
        
    except Exception as e:
        print(f"Error en activos_por_fecha: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/activos_por_usuario_semana')
def activos_por_usuario_semana():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    usuario_id = request.args.get('usuario_id', 'todos')
    cursor = db.conn.cursor()
    
    try:
        # Construir filtro de usuario
        filtro_usuario = ""
        params = []
        if usuario_id and usuario_id != 'todos':
            filtro_usuario = "AND a.IdUsuario = %s"
            params.append(usuario_id)
        
        # Query para activos por semana (últimos 90 días)
        query = f"""
            SELECT 
                DATE_TRUNC('week', a.FechaEntrada) as semana_inicio,
                COUNT(*) as cantidad,
                p.NombreCompleto as nombre_usuario
            FROM Activos a
            JOIN Usuarios u ON a.IdUsuario = u.idUsuario
            JOIN Personas p ON u.idPersona = p.idPersona
            WHERE a.FechaEntrada >= NOW() - INTERVAL '90 days'
            {filtro_usuario}
            GROUP BY DATE_TRUNC('week', a.FechaEntrada), p.NombreCompleto
            ORDER BY semana_inicio
        """
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        semanas = []
        cantidades = []
        
        for r in resultados:
            fecha_inicio = r[0].strftime('%Y-%m-%d')
            fecha_fin = (r[0] + timedelta(days=6)).strftime('%Y-%m-%d')
            semanas.append(f"{fecha_inicio} al {fecha_fin}")
            cantidades.append(r[1])
        
        # Obtener lista de usuarios para el filtro (con nombre completo)
        cursor.execute("""
            SELECT u.idUsuario, u."User", p.NombreCompleto 
            FROM Usuarios u
            JOIN Personas p ON u.idPersona = p.idPersona
            ORDER BY p.NombreCompleto
        """)
        usuarios = cursor.fetchall()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM Activos WHERE FechaEntrada >= NOW() - INTERVAL '90 days'")
        total_activos_periodo = cursor.fetchone()[0]
        
        # Usuario más activo (con nombre completo)
        cursor.execute("""
            SELECT p.NombreCompleto, COUNT(*) as cantidad
            FROM Activos a
            JOIN Usuarios u ON a.IdUsuario = u.idUsuario
            JOIN Personas p ON u.idPersona = p.idPersona
            WHERE a.FechaEntrada >= NOW() - INTERVAL '90 days'
            GROUP BY p.NombreCompleto
            ORDER BY cantidad DESC
            LIMIT 1        """)
        top_usuario = cursor.fetchone()
        
        return jsonify({
            'semanas': semanas,
            'cantidades': cantidades,
            'total_activos': total_activos_periodo,
            'top_usuario': top_usuario[0] if top_usuario else 'N/A',  # ← AHORA ES NOMBRE COMPLETO
            'top_cantidad': top_usuario[1] if top_usuario else 0,
            'usuarios': [{'id': u[0], 'username': u[1], 'nombre': u[2]} for u in usuarios]
        })
        
    except Exception as e:
        print(f"Error en activos_por_usuario_semana: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats_usuario/<int:usuario_id>')
def stats_usuario(usuario_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    cursor = db.conn.cursor()
    
    try:
        # Total de activos del usuario
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Activos 
            WHERE IdUsuario = %s AND FechaEntrada >= NOW() - INTERVAL '90 days'
        """, (usuario_id,))
        total_activos = cursor.fetchone()[0]
        
        # Semana con más activos
        cursor.execute("""
            SELECT 
                DATE_TRUNC('week', FechaEntrada) as semana,
                COUNT(*) as cantidad
            FROM Activos
            WHERE IdUsuario = %s AND FechaEntrada >= NOW() - INTERVAL '90 days'
            GROUP BY DATE_TRUNC('week', FechaEntrada)
            ORDER BY cantidad DESC
            LIMIT 1        """, (usuario_id,))
        top_semana = cursor.fetchone()
        
        return jsonify({
            'total_activos': total_activos,
            'top_semana': top_semana[0].strftime('%Y-%m-%d') if top_semana else None,
            'top_cantidad': top_semana[1] if top_semana else 0
        })
        
    except Exception as e:
        print(f"Error en stats_usuario: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/movimientos_por_semana')
def movimientos_por_semana():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    usuario_id = request.args.get('usuario_id', 'todos')
    cursor = db.conn.cursor()
    
    try:
        # Construir filtro de usuario
        filtro_usuario = ""
        params = []
        if usuario_id and usuario_id != 'todos':
            filtro_usuario = "AND h.idUsuario = %s"
            params.append(usuario_id)
        
        # Query para movimientos por semana (últimos 90 días)
        query = f"""
            SELECT 
                DATE_TRUNC('week', h.FechaEdicion) as semana_inicio,
                COUNT(*) as cantidad,
                p.NombreCompleto as nombre_usuario
            FROM Historial h
            JOIN Usuarios u ON h.idUsuario = u.idUsuario
            JOIN Personas p ON u.idPersona = p.idPersona
            WHERE h.FechaEdicion >= NOW() - INTERVAL '90 days'
            {filtro_usuario}
            GROUP BY DATE_TRUNC('week', h.FechaEdicion), p.NombreCompleto
            ORDER BY semana_inicio
        """
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        semanas = []
        cantidades = []
        
        for r in resultados:
            fecha_inicio = r[0].strftime('%Y-%m-%d')
            fecha_fin = (r[0] + timedelta(days=6)).strftime('%Y-%m-%d')
            semanas.append(f"{fecha_inicio} al {fecha_fin}")
            cantidades.append(r[1])
        
        # Obtener lista de usuarios para el filtro
        cursor.execute("""
            SELECT u.idUsuario, u."User", p.NombreCompleto 
            FROM Usuarios u
            JOIN Personas p ON u.idPersona = p.idPersona
            ORDER BY p.NombreCompleto
        """)
        usuarios = cursor.fetchall()
        
        # Estadísticas generales
        cursor.execute("SELECT COUNT(*) FROM Historial WHERE FechaEdicion >= NOW() - INTERVAL '90 days'")
        total_movimientos_periodo = cursor.fetchone()[0]
        
        # Usuario con más movimientos
        cursor.execute("""
            SELECT p.NombreCompleto, COUNT(*) as cantidad
            FROM Historial h
            JOIN Usuarios u ON h.idUsuario = u.idUsuario
            JOIN Personas p ON u.idPersona = p.idPersona
            WHERE h.FechaEdicion >= NOW() - INTERVAL '90 days'
            GROUP BY p.NombreCompleto
            ORDER BY cantidad DESC
            LIMIT 1        """)
        top_usuario = cursor.fetchone()
        
        return jsonify({
            'semanas': semanas,
            'cantidades': cantidades,
            'total_movimientos': total_movimientos_periodo,
            'top_usuario': top_usuario[0] if top_usuario else 'N/A',
            'top_cantidad': top_usuario[1] if top_usuario else 0,
            'usuarios': [{'id': u[0], 'username': u[1], 'nombre': u[2]} for u in usuarios]
        })
        
    except Exception as e:
        print(f"Error en movimientos_por_semana: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats_movimientos_usuario/<int:usuario_id>')
def stats_movimientos_usuario(usuario_id):
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    cursor = db.conn.cursor()
    
    try:
        # Total de movimientos del usuario
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Historial 
            WHERE idUsuario = %s AND FechaEdicion >= NOW() - INTERVAL '90 days'
        """, (usuario_id,))
        total_movimientos = cursor.fetchone()[0]
        
        # Semana con más movimientos
        cursor.execute("""
            SELECT 
                DATE_TRUNC('week', FechaEdicion) as semana,
                COUNT(*) as cantidad
            FROM Historial
            WHERE idUsuario = %s AND FechaEdicion >= NOW() - INTERVAL '90 days'
            GROUP BY DATE_TRUNC('week', FechaEdicion)
            ORDER BY cantidad DESC
            LIMIT 1        """, (usuario_id,))
        top_semana = cursor.fetchone()
        
        return jsonify({
            'total_movimientos': total_movimientos,
            'top_semana': top_semana[0].strftime('%Y-%m-%d') if top_semana else None,
            'top_cantidad': top_semana[1] if top_semana else 0
        })
        
    except Exception as e:
        print(f"Error en stats_movimientos_usuario: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/movimientos_stats')
def movimientos_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Historial")
        resultado = cursor.fetchone()
        
        total_movimientos = resultado[0] if resultado else 0
        
        return jsonify({
            'total': total_movimientos
        })
        
    except Exception as e:
        print(f"Error en movimientos_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/activos_por_antiguedad')
def activos_por_antiguedad():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        cursor = db.conn.cursor()
        # Obtener activos ordenados por fecha (más antiguos primero)
        cursor.execute("""
            SELECT                 a.idActivo,
                a.Nombre,
                a.FechaEntrada,
                a.HoraEntrada,
                e.Edificio,
                a.UbicacionActual,
                a.Garantia,
                EXTRACT(EPOCH FROM (NOW() - a.FechaEntrada))::int/86400 as dias_desde_ingreso,
                CASE 
                    WHEN a.Garantia IS NOT NULL AND a.Garantia != '' 
                    THEN 'Con garantía' 
                    ELSE 'Sin garantía' 
                END as estado_garantia
            FROM Activos a
            LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
            ORDER BY a.FechaEntrada ASC, a.HoraEntrada ASC
        """)
        
        activos = cursor.fetchall()
        
        # Estadísticas
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Activos")
        total_activos = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Activos WHERE Garantia IS NOT NULL AND Garantia != ''")
        total_garantias = cursor.fetchone()[0]
        
        # Activo más antiguo
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT Nombre, FechaEntrada
            FROM Activos
            ORDER BY FechaEntrada ASC, HoraEntrada ASC
            LIMIT 1        """)
        mas_antiguo = cursor.fetchone()
        
        activo_mas_antiguo = mas_antiguo[0] if mas_antiguo else 'N/A'
        fecha_mas_antigua = mas_antiguo[1].strftime('%Y-%m-%d') if mas_antiguo and mas_antiguo[1] else ''
        
        return jsonify({
            'total_activos': total_activos,
            'total_garantias': total_garantias,
            'activo_mas_antiguo': activo_mas_antiguo,
            'fecha_mas_antigua': fecha_mas_antigua,
            'activos': [{
                'id': a[0],
                'nombre': a[1],
                'fecha': a[2].strftime('%Y-%m-%d') if a[2] else 'N/A',
                'hora': str(a[3]) if a[3] else 'N/A',
                'edificio': a[4] or 'Sin edificio',
                'ubicacion': a[5] or 'N/A',
                'garantia': a[6] or 'Sin garantía',
                'dias': a[7],
                'estado': a[8]
            } for a in activos]
        })
        
    except Exception as e:
        print(f"Error en activos_por_antiguedad: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/activos_antiguos_stats')
def activos_antiguos_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN EXTRACT(EPOCH FROM (NOW() - FechaEntrada))::int/86400 <= 30 THEN 1 ELSE 0 END) as ultimo_mes,
                SUM(CASE WHEN EXTRACT(EPOCH FROM (NOW() - FechaEntrada))::int/86400 BETWEEN 31 AND 90 THEN 1 ELSE 0 END) as uno_tres_meses,
                SUM(CASE WHEN EXTRACT(EPOCH FROM (NOW() - FechaEntrada))::int/86400 BETWEEN 91 AND 180 THEN 1 ELSE 0 END) as tres_seis_meses,
                SUM(CASE WHEN EXTRACT(EPOCH FROM (NOW() - FechaEntrada))::int/86400 > 180 THEN 1 ELSE 0 END) as mas_seis_meses
            FROM Activos
        """)
        
        stats = cursor.fetchone()
        
        return jsonify({
            'ultimo_mes': stats[0] or 0,
            'uno_tres_meses': stats[1] or 0,
            'tres_seis_meses': stats[2] or 0,
            'mas_seis_meses': stats[3] or 0
        })
        
    except Exception as e:
        print(f"Error en activos_antiguos_stats: {e}")
        return jsonify({'error': str(e)}), 500

# =========================================
# API PÚBLICAS (sin autenticación para el cliente web 2)
# =========================================

@app.route('/api/public/simple_stats')
def public_simple_stats():
    """Versión usando el mismo patrón que activos_por_antiguedad"""
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Activos")
        total_activos = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        total_usuarios = cursor.fetchone()[0]
        
        cursor = db.conn.cursor()
        cursor.execute("""
                SELECT Nombre, FechaEntrada
                FROM Activos
                ORDER BY FechaEntrada ASC, HoraEntrada ASC
                LIMIT 1
            """)
        mas_antiguo = cursor.fetchone()
        
        activo_mas_antiguo = mas_antiguo[0] if mas_antiguo else 'Ninguno'
        fecha_mas_antigua = mas_antiguo[1].strftime('%Y-%m-%d') if mas_antiguo and mas_antiguo[1] else ''
        
        return jsonify({
            'activos': total_activos,
            'usuarios': total_usuarios,
            'movimientos': 0,
            'garantias': 0,
            'administradores': 0,
            'activo_mas_antiguo': activo_mas_antiguo,
            'fecha_mas_antigua': fecha_mas_antigua
        })
        
    except Exception as e:
        print(f"Error en simple_stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/public/activos_por_antiguedad')
def public_activos_por_antiguedad():
    """Versión pública de activos_por_antiguedad"""
    try:
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT                 a.idActivo,
                a.Nombre,
                a.FechaEntrada,
                a.HoraEntrada,
                e.Edificio,
                a.UbicacionActual,
                a.Garantia,
                EXTRACT(EPOCH FROM (NOW() - a.FechaEntrada))::int/86400 as dias_desde_ingreso,
                CASE 
                    WHEN a.Garantia IS NOT NULL AND a.Garantia != '' 
                    THEN 'Con garantía' 
                    ELSE 'Sin garantía' 
                END as estado_garantia
            FROM Activos a
            LEFT JOIN Edificios e ON a.IdEdificio = e.idEdificio
            ORDER BY a.FechaEntrada ASC, a.HoraEntrada ASC
        """)
        
        activos = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM Activos")
        total_activos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Activos WHERE Garantia IS NOT NULL AND Garantia != ''")
        total_garantias = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT Nombre, FechaEntrada
            FROM Activos
            ORDER BY FechaEntrada ASC, HoraEntrada ASC
            LIMIT 1        """)
        mas_antiguo = cursor.fetchone()
        
        # NO cerrar el cursor
        
        activo_mas_antiguo = mas_antiguo[0] if mas_antiguo else 'N/A'
        fecha_mas_antigua = mas_antiguo[1].strftime('%Y-%m-%d') if mas_antiguo and mas_antiguo[1] else ''
        
        activos_list = []
        for a in activos:
            activos_list.append({
                'id': a[0],
                'nombre': a[1] if a[1] else 'Sin nombre',
                'fecha': a[2].strftime('%Y-%m-%d') if a[2] else 'N/A',
                'hora': str(a[3]) if a[3] else 'N/A',
                'edificio': a[4] if a[4] else 'Sin edificio',
                'ubicacion': a[5] if a[5] else 'N/A',
                'garantia': a[6] if a[6] else 'Sin garantía',
                'dias': a[7] if a[7] else 0,
                'estado': a[8] if a[8] else 'Sin garantía'
            })
        
        return jsonify({
            'total_activos': total_activos,
            'total_garantias': total_garantias,
            'activo_mas_antiguo': activo_mas_antiguo,
            'fecha_mas_antigua': fecha_mas_antigua,
            'activos': activos_list
        })
        
    except Exception as e:
        print(f"Error en public_activos_por_antiguedad: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

