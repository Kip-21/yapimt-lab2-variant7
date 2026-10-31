.386
.MODEL FLAT, STDCALL
.STACK 4096

EXTERN GetStdHandle@4:PROC
EXTERN SetConsoleCP@4:PROC
EXTERN SetConsoleOutputCP@4:PROC
EXTERN ReadConsoleA@20:PROC
EXTERN WriteConsoleA@20:PROC
EXTERN ExitProcess@4:PROC

MAX_LENGTH EQU 255

.DATA
prompt       DB 'Enter a string (max 255 characters): '
promptLength EQU $ - prompt
resultText   DB 'Palindrome: '
resultLength EQU $ - resultText
errorText    DB 'Error: input failed or string is longer than 255 characters.',13,10
errorLength  EQU $ - errorText
inputHandle  DD ?
outputHandle DD ?
readCount    DD ?
written      DD ?
stringLength DD ?
inputBuffer  DB MAX_LENGTH + 3 DUP (?)
outputBuffer DB 2 * MAX_LENGTH + 2 DUP (?)

.CODE
; Вывод EDX байтов из буфера с адресом EAX.
PrintText PROC
    PUSH 0
    PUSH OFFSET written
    PUSH EDX
    PUSH EAX
    PUSH outputHandle
    CALL WriteConsoleA@20
    RET
PrintText ENDP

MAIN PROC
    CLD
    ; В CP866 русская буква занимает один байт.
    PUSH 866
    CALL SetConsoleCP@4
    PUSH 866
    CALL SetConsoleOutputCP@4

    PUSH -10
    CALL GetStdHandle@4
    MOV inputHandle, EAX
    PUSH -11
    CALL GetStdHandle@4
    MOV outputHandle, EAX

    MOV EAX, OFFSET prompt
    MOV EDX, promptLength
    CALL PrintText

    PUSH 0
    PUSH OFFSET readCount
    PUSH SIZEOF inputBuffer
    PUSH OFFSET inputBuffer
    PUSH inputHandle
    CALL ReadConsoleA@20
    TEST EAX, EAX
    JZ inputError

    ; Консоль добавляет CR и LF; они не входят в исходную строку.
    MOV ECX, readCount
    CMP ECX, 2
    JB inputError
    SUB ECX, 2
    CMP ECX, MAX_LENGTH
    JA inputError
    CMP BYTE PTR inputBuffer[ECX], 13
    JNE inputError
    CMP BYTE PTR inputBuffer[ECX+1], 10
    JNE inputError
    MOV stringLength, ECX

    ; Копирование исходной строки.
    CLD
    MOV ESI, OFFSET inputBuffer
    MOV EDI, OFFSET outputBuffer
    REP MOVSB

    ; Дописывание символов в обратном порядке.
    MOV ECX, stringLength
    JECXZ palindromeReady
    LEA ESI, inputBuffer[ECX-1]
copyBackwards:
    STD
    LODSB
    CLD
    STOSB
    LOOP copyBackwards

palindromeReady:
    ; Добавление перевода строки.
    MOV AL, 13
    STOSB
    MOV AL, 10
    STOSB

    MOV EAX, OFFSET resultText
    MOV EDX, resultLength
    CALL PrintText

    MOV EAX, OFFSET outputBuffer
    MOV EDX, stringLength
    ADD EDX, EDX
    ADD EDX, 2
    CALL PrintText

    PUSH 0
    CALL ExitProcess@4

inputError:
    MOV EAX, OFFSET errorText
    MOV EDX, errorLength
    CALL PrintText
    PUSH 1
    CALL ExitProcess@4
MAIN ENDP
END MAIN
