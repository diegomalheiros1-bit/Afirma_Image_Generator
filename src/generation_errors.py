"""Allowlisted diagnostics: never serialize SDK bodies, headers or raw messages."""
import math
import re

from openai import APITimeoutError, APIConnectionError, APIStatusError, APIResponseValidationError


KNOWN_CODES = {
    'invalid_api_key', 'permission_denied', 'invalid_request_error', 'invalid_value',
    'unsupported_parameter', 'model_not_found', 'content_policy_violation', 'moderation_blocked',
    'insufficient_quota', 'credit_balance_exhausted', 'organization_usage_limit_exceeded',
    'organization_spend_limit_exceeded', 'project_spend_limit_exceeded',
    'rate_limit_exceeded', 'slow_down', 'server_is_overloaded',
}
CATEGORIES = {
    'timeout', 'connection', 'authentication', 'permission', 'parameters', 'limit_quota',
    'server', 'http_error', 'invalid_image', 'storage', 'unexpected', 'local_validation',
}
SAFE_TYPES = {
    'APITimeoutError', 'APIConnectionError', 'APIStatusError', 'APIResponseValidationError',
    'BadRequestError', 'AuthenticationError', 'PermissionDeniedError', 'NotFoundError',
    'ConflictError', 'UnprocessableEntityError', 'RateLimitError', 'InternalServerError',
    'APIError', 'GenerationError', 'OutputStorageError', 'Exception', 'RuntimeError',
    'ValueError', 'TypeError', 'AttributeError', 'KeyError', 'OSError', 'PermissionError',
    'FileExistsError', 'FileNotFoundError', 'UnidentifiedImageError', 'Error',
}


def safe_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(r'req_[A-Za-z0-9_-]{1,120}', value) else None


def sanitize_diagnostic(values):
    if not isinstance(values, dict):
        values = {}
    category, exception_type = values.get('category'), values.get('exception_type')
    result = {'category': category if isinstance(category, str) and category in CATEGORIES else 'unexpected',
              'exception_type': exception_type if isinstance(exception_type, str) and exception_type in SAFE_TYPES else 'Exception',
              'uncertain': values.get('uncertain', True) is not False}
    status = values.get('http_status')
    if type(status) is int and 100 <= status <= 599:
        result['http_status'] = status
    code = values.get('api_code')
    if isinstance(code, str) and code in KNOWN_CODES:
        result['api_code'] = code
    request_id = safe_request_id(values.get('request_id'))
    if request_id:
        result['request_id'] = request_id
    for key in ('elapsed_seconds', 'timeout_seconds'):
        value = values.get(key)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            result[key] = round(value, 3)
    attempts = values.get('api_attempts')
    if type(attempts) is int and attempts >= 0:
        result['api_attempts'] = attempts
    return result


def classify_exception(exc, *, timeout=None, attempts=0, elapsed=None, request_id=None):
    values = dict(category='unexpected', exception_type=type(exc).__name__, uncertain=True,
                  timeout_seconds=timeout, api_attempts=attempts, elapsed_seconds=elapsed,
                  request_id=request_id)
    # APITimeoutError inherits APIConnectionError; order is significant.
    if isinstance(exc, APITimeoutError):
        values['category'] = 'timeout'
    elif isinstance(exc, APIConnectionError):
        values['category'] = 'connection'
    elif isinstance(exc, APIResponseValidationError):
        values['category'] = 'invalid_image'
        values.update(http_status=exc.status_code,
                      request_id=exc.response.headers.get('x-request-id'))
    elif isinstance(exc, APIStatusError):
        status = exc.status_code
        code = exc.code if isinstance(exc.code, str) and exc.code in KNOWN_CODES else None
        transient = (status == 429 and code in {'rate_limit_exceeded', 'slow_down'} or
                     status == 503 and code == 'server_is_overloaded')
        values.update(http_status=status, api_code=code, request_id=exc.request_id,
                      uncertain=status == 408 or status >= 500 and not transient,
                      category={401: 'authentication', 403: 'permission', 400: 'parameters',
                                404: 'parameters', 422: 'parameters', 429: 'limit_quota',
                                408: 'timeout'}.get(status, 'server' if status >= 500 else 'http_error'))
    return sanitize_diagnostic(values)


def error_message(details):
    category = details['category']
    if category == 'timeout':
        timeout = details.get('timeout_seconds')
        limit = f' de {timeout:g} segundos' if timeout is not None else ''
        message = f'Limite de espera{limit} atingido; o processamento remoto não foi confirmado.'
    else:
        message = {
            'connection': 'Falha de conexão com a OpenAI; o processamento remoto não foi confirmado.',
            'authentication': 'OpenAI: autenticação recusada; confira a chave da API.',
            'permission': 'OpenAI: permissão recusada; confira o acesso ao projeto e ao modelo.',
            'parameters': 'OpenAI: parâmetros recusados; confira a configuração e as referências.',
            'limit_quota': 'OpenAI: limite/quota atingido; confira faturamento e limites.',
            'server': 'OpenAI: erro do servidor; confira o histórico antes de uma nova execução.',
            'http_error': 'OpenAI: requisição recusada; confira o código HTTP no diagnóstico.',
            'invalid_image': 'Resposta de imagem inválida; o resultado exige revisão antes de reenviar.',
            'storage': 'Falha local ao gravar a imagem; preserve as saídas existentes para revisão.',
            'local_validation': 'Falha na validação local; confira os arquivos antes de tentar novamente.',
            'unexpected': 'Erro inesperado após iniciar a geração; o resultado exige revisão.',
        }[category]
    if details['uncertain']:
        message += ' Nenhuma repetição automática; item em REVISAO.'
    return message


def interruption_reason(category):
    cause = {'timeout': 'timeout', 'connection': 'falha de conexão', 'server': 'erro do servidor',
             'invalid_image': 'resposta de imagem inválida', 'storage': 'falha local de armazenamento'}
    return 'Interrompido para revisão após ' + cause.get(category, 'erro inesperado')
