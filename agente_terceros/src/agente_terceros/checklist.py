"""Catálogo de controles ISO/IEC 27701:2025 y cláusulas mínimas de un DPA.

La norma ISO no es de libre acceso: aquí solo se catalogan los títulos de los
controles y una paráfrasis propia. La numeración 2025 se infiere de la
correspondencia con la edición 2019 (Anexo F): tabla A.1 (responsable) = 7.x,
tabla A.2 (encargado) = 8.x, con el último dígito desplazado en uno.
Verificar contra el texto oficial antes de citarla en un informe formal.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Control:
    ref: str
    titulo: str
    rol: str  # "responsable" | "encargado"
    ref_2019: str
    resumen: str


CONTROLES = (
    Control("A.1.2.7", "Contratos con encargados del tratamiento", "responsable", "7.2.6",
            "El contrato con el encargado incluye la implementación de los controles "
            "apropiados de la tabla A.2 según el tratamiento encargado."),
    Control("A.1.2.8", "Responsable conjunto del tratamiento", "responsable", "7.2.7",
            "Se definen roles y responsabilidades frente a otro responsable conjunto."),
    Control("A.1.5.4", "Registros de transferencia de PII", "responsable", "7.5.3",
            "Se registran las transferencias de PII hacia o desde terceros."),
    Control("A.2.2.2", "Acuerdo con el cliente", "encargado", "8.2.1",
            "El contrato con el cliente asegura que el encargado le asiste en sus obligaciones."),
    Control("A.2.2.3", "Finalidades de la organización", "encargado", "8.2.2",
            "La PII se trata solo para las finalidades indicadas en las instrucciones documentadas."),
    Control("A.2.2.5", "Instrucción infractora", "encargado", "8.2.4",
            "El encargado informa al cliente si una instrucción infringe la normativa."),
    Control("A.2.2.6", "Obligaciones del cliente", "encargado", "8.2.5",
            "El encargado proporciona información para demostrar cumplimiento (auditorías)."),
    Control("A.2.2.7", "Registros del tratamiento de PII", "encargado", "8.2.6",
            "El encargado mantiene registros del tratamiento realizado por cuenta del cliente."),
    Control("A.2.3.2", "Obligaciones con los titulares de PII", "encargado", "8.3.1",
            "El encargado facilita al cliente atender los derechos de los titulares."),
    Control("A.2.4.3", "Devolución, transferencia o eliminación de PII", "encargado", "8.4.2",
            "Política para devolver, transferir o eliminar la PII al terminar el servicio."),
    Control("A.2.4.4", "Controles de transmisión de PII", "encargado", "8.4.3",
            "La PII transmitida por redes se protege para llegar a su destino previsto."),
    Control("A.2.5.2", "Base para la transferencia de PII entre jurisdicciones", "encargado", "8.5.1",
            "Se informa al cliente de la base legal de las transferencias internacionales."),
    Control("A.2.5.3", "Países y organizaciones a los que se puede transferir PII", "encargado", "8.5.2",
            "Se especifican y documentan los países de destino de la PII."),
    Control("A.2.5.5", "Notificación de solicitudes de divulgación de PII", "encargado", "8.5.4",
            "Se notifica al cliente de solicitudes legalmente vinculantes de divulgación."),
    Control("A.2.5.7", "Divulgación de subcontratistas usados para tratar PII", "encargado", "8.5.6",
            "El encargado comunica al cliente el uso de subencargados antes de emplearlos."),
    Control("A.2.5.8", "Contratación de un subcontratista para tratar PII", "encargado", "8.5.7",
            "Solo se contrata a subencargados conforme al contrato con el cliente."),
    Control("A.2.5.9", "Cambio de subcontratista para tratar PII", "encargado", "8.5.8",
            "Se informa al cliente de cambios de subencargado para que pueda oponerse."),
)

CONTROLES_ISO: dict[str, Control] = {c.ref: c for c in CONTROLES}


@dataclass(frozen=True)
class Clausula:
    """Requisito mínimo que un contrato de encargo (DPA) debe contemplar."""

    id: str
    titulo: str
    criterio: str  # qué debe decir el contrato para considerarse cumplido
    consulta: str  # consulta para recuperar el fundamento normativo
    rgpd: str
    peru: str
    iso: tuple[str, ...]
    peso: int  # 3 = esencial, 2 = importante, 1 = recomendable


CLAUSULAS: tuple[Clausula, ...] = (
    Clausula(
        "objeto_duracion",
        "Objeto, duración, naturaleza y finalidad del tratamiento",
        "Describe el objeto, la duración, la naturaleza y la finalidad del tratamiento, "
        "el tipo de datos personales y las categorías de titulares.",
        "contenido del contrato de encargo: objeto, duración, naturaleza, finalidad, tipo de datos y categorías de interesados",
        "Art. 28.3", "LPDP art. 30", ("A.1.2.7", "A.2.2.3"), 3,
    ),
    Clausula(
        "instrucciones",
        "Tratamiento solo según instrucciones documentadas",
        "El encargado trata los datos únicamente siguiendo instrucciones documentadas del "
        "responsable y le informa si una instrucción infringe la normativa.",
        "el encargado tratará los datos personales únicamente siguiendo instrucciones documentadas del responsable",
        "Art. 28.3.a, 29", "LPDP art. 30; RLPDP art. 30.2", ("A.2.2.3", "A.2.2.5"), 3,
    ),
    Clausula(
        "confidencialidad",
        "Confidencialidad del personal autorizado",
        "Las personas autorizadas a tratar los datos se comprometen a respetar la "
        "confidencialidad o están sujetas a una obligación legal de confidencialidad.",
        "personas autorizadas para tratar datos personales se han comprometido a respetar la confidencialidad",
        "Art. 28.3.b", "LPDP art. 17", ("A.2.2.2",), 2,
    ),
    Clausula(
        "seguridad",
        "Medidas técnicas y organizativas de seguridad",
        "El encargado adopta medidas de seguridad apropiadas (art. 32 RGPD) y las detalla "
        "o referencia en un anexo.",
        "medidas técnicas y organizativas de seguridad que debe adoptar el encargado del tratamiento",
        "Art. 28.3.c, 32", "LPDP art. 16; RLPDP art. 30.3", ("A.2.2.2", "A.2.4.4"), 3,
    ),
    Clausula(
        "subencargados",
        "Subencargados: autorización previa y aviso de cambios",
        "No recurre a otro encargado sin autorización previa (específica o general) del "
        "responsable, le informa de cambios para que pueda oponerse e impone al "
        "subencargado las mismas obligaciones.",
        "subcontratación de otro encargado: autorización previa por escrito, información de cambios y mismas obligaciones",
        "Art. 28.2, 28.4", "RLPDP arts. 31.1, 32 y 33", ("A.2.5.7", "A.2.5.8", "A.2.5.9"), 3,
    ),
    Clausula(
        "derechos_titulares",
        "Asistencia para atender derechos de los titulares",
        "El encargado asiste al responsable, mediante medidas apropiadas, para responder "
        "a las solicitudes de ejercicio de derechos de los titulares.",
        "el encargado asistirá al responsable para responder a las solicitudes de ejercicio de los derechos de los interesados",
        "Art. 28.3.e", "LPDP arts. 18-27", ("A.2.3.2",), 2,
    ),
    Clausula(
        "notificacion_brechas",
        "Notificación de incidentes de seguridad",
        "El encargado notifica al responsable sin dilación indebida (o en un plazo "
        "concreto) los incidentes de seguridad y le asiste en la notificación a la autoridad.",
        "el encargado notificará al responsable sin dilación las violaciones de seguridad de los datos personales",
        "Art. 28.3.f, 33.2", "RLPDP arts. 34 y 36", ("A.2.2.2", "A.2.2.6"), 3,
    ),
    Clausula(
        "supresion_devolucion",
        "Supresión o devolución al terminar el servicio",
        "Al finalizar la prestación, el encargado suprime o devuelve los datos (a elección "
        "del responsable) y evidencia la supresión, salvo obligación legal de conservarlos.",
        "al finalizar la prestación de servicios el encargado suprimirá o devolverá todos los datos personales",
        "Art. 28.3.g", "LPDP art. 30; RLPDP arts. 30.4 y 31.2", ("A.2.4.3",), 3,
    ),
    Clausula(
        "auditorias",
        "Información y auditorías del responsable",
        "El encargado pone a disposición la información necesaria para demostrar el "
        "cumplimiento y permite auditorías o inspecciones del responsable.",
        "el encargado permitirá y contribuirá a la realización de auditorías e inspecciones por parte del responsable",
        "Art. 28.3.h", "RLPDP art. 30", ("A.2.2.6", "A.2.2.7"), 2,
    ),
    Clausula(
        "transferencias",
        "Transferencias internacionales",
        "Indica los países de destino y la base legal (nivel adecuado, cláusulas tipo, "
        "consentimiento) de cualquier transferencia internacional.",
        "transferencias internacionales de datos personales a terceros países: nivel adecuado de protección y garantías",
        "Arts. 44-46", "LPDP art. 15; RLPDP arts. 12-14", ("A.2.5.2", "A.2.5.3", "A.1.5.4"), 2,
    ),
    Clausula(
        "limitacion_finalidad",
        "Prohibición de uso para fines propios o comunicación a terceros",
        "El encargado no usa los datos para fines propios ni los comunica a terceros, ni "
        "siquiera para su conservación, salvo autorización del responsable.",
        "el encargado no podrá utilizar los datos para un fin distinto ni transferirlos a otras personas ni para su conservación",
        "Art. 28.10", "LPDP art. 30; RLPDP arts. 29.2 y 33", ("A.2.2.3",), 3,
    ),
    Clausula(
        "solicitudes_autoridad",
        "Aviso de solicitudes de divulgación de autoridades",
        "El encargado informa al responsable de cualquier solicitud legalmente vinculante "
        "de divulgación de datos, salvo prohibición legal.",
        "solicitud de acceso a los datos por autoridad competente: informar al responsable",
        "Art. 28.3.a", "RLPDP art. 30.5", ("A.2.5.5",), 1,
    ),
    Clausula(
        "eipd_asistencia",
        "Asistencia en evaluaciones de impacto y consultas previas",
        "El encargado ayuda al responsable a realizar evaluaciones de impacto y consultas "
        "previas, considerando la información a su disposición.",
        "el encargado ayudará al responsable a garantizar el cumplimiento de la evaluación de impacto y la consulta previa",
        "Art. 28.3.f, 35-36", "RLPDP art. 40", ("A.2.2.2",), 1,
    ),
)

_POR_ID = {c.id: c for c in CLAUSULAS}


def por_id(clausula_id: str) -> Clausula:
    return _POR_ID[clausula_id]
