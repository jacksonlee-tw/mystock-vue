-- ============================================
-- Database: openSQLDB
-- Server:   192.168.153.12
-- Generated DDL for all user tables
-- ============================================
 
 
 
-- ----------------------------------------
-- Table: [dbo].[CMM_SCALE]
-- ----------------------------------------
CREATE TABLE [dbo].[CMM_SCALE] (
    [compNo] VARCHAR(4) NOT NULL,
    [plantNo] CHAR(4) NOT NULL,
    [DBNo] VARCHAR(10) NOT NULL,
    [TruckNo] VARCHAR(20) NULL,
    [RTruckNo] VARCHAR(20) NULL,
    [potype] VARCHAR(20) NULL,
    [PoNo] VARCHAR(20) NOT NULL,
    [RPoNo] VARCHAR(20) NULL,
    [prodName] NVARCHAR(40) NULL,
    [RprodName] NVARCHAR(40) NULL,
    [Net] INT NULL,
    [RNet] BIGINT NULL,
    [supply] NVARCHAR(35) NULL,
    [RSupply] NVARCHAR(35) NULL,
    [SNet] BIGINT NULL,
    [RSNet] BIGINT NULL,
    [NNet] BIGINT NULL,
    [RNNet] BIGINT NULL,
    [ArrDate] VARCHAR(8) NULL,
    [ArrTime] VARCHAR(6) NULL,
    [LeftDate] VARCHAR(8) NULL,
    [LeftTime] VARCHAR(6) NULL,
    [WHNo] VARCHAR(4) NULL,
    [abFlag] NVARCHAR(1) NULL,
    [abReason] VARCHAR(50) NULL,
    [absultion] VARCHAR(10) NULL,
    [SpecUserNo] VARCHAR(20) NULL,
    [version] INT NOT NULL DEFAULT ((0)),
    [ABUserNo] NVARCHAR(10) NULL,
    [Instatus] VARCHAR(1) NULL,
    [OutStatus] VARCHAR(1) NULL,
    [TaskProc] VARCHAR(10) NULL,
    [printNum] INT NULL,
    [WeightMan1] NVARCHAR(50) NULL,
    [WeightMan2] NVARCHAR(50) NULL,
    [weightman3] NVARCHAR(50) NULL,
    [weightman4] NVARCHAR(50) NULL,
    [tranflag] NVARCHAR(50) NULL,
    [isCancel] NVARCHAR(50) NULL,
    [FTare] NVARCHAR(50) NULL,
    [TTare] NVARCHAR(50) NULL,
    [FNet] NVARCHAR(50) NULL,
    [TNet] NVARCHAR(50) NULL,
    [underwrite] NVARCHAR(50) NULL,
    [PortNo1] NVARCHAR(3) NULL,
    [portNo2] NVARCHAR(3) NULL,
    [portNo3] NVARCHAR(3) NULL,
    [portNo4] NVARCHAR(3) NULL,
    [InStoreTime] DATETIME NULL,
    [outStoreTime] DATETIME NULL,
    [weigth1] INT NULL,
    [weigth2] INT NULL,
    [weigth3] INT NULL,
    [weigth4] INT NULL,
    [absultion2] VARCHAR(10) NULL,
    [SpecUserNo2] VARCHAR(10) NULL,
    [abReason2] VARCHAR(50) NULL,
    [CalType] INT NULL,
    [OutPrintNum] INT NULL,
    [workFlow] CHAR(1) NULL,
    [BoatNo] VARCHAR(20) NULL DEFAULT (''),
    [Drivers] VARCHAR(40) NULL,
    [DelReason] VARCHAR(40) NULL,
    [DelFlag] BIT NULL DEFAULT ((0)),
    [BatchNo] VARCHAR(50) NULL,
    [WgtMax] VARCHAR(10) NULL,
    [SEQ_NO] VARCHAR(3) NULL DEFAULT ((1)),
    [Marks] VARCHAR(40) NULL,
    [TRANCOMP] VARCHAR(40) NULL,
    [MTel] VARCHAR(20) NULL,
    CONSTRAINT [PK__CMM_SCAL__C8FD5C54E46F698B] PRIMARY KEY ([compNo], [plantNo], [DBNo], [version])
);
GO
  
 

-- ----------------------------------------
-- Table: [dbo].[CMM_SCALE_History]
-- ----------------------------------------
CREATE TABLE [dbo].[CMM_SCALE_History] (
    [compNo] VARCHAR(4) NULL,
    [plantNo] CHAR(4) NULL,
    [DBNo] VARCHAR(10) NOT NULL,
    [TruckNo] VARCHAR(20) NULL,
    [RTruckNo] VARCHAR(20) NULL,
    [potype] VARCHAR(20) NULL,
    [PoNo] VARCHAR(12) NULL,
    [RPoNo] VARCHAR(12) NULL,
    [prodName] NVARCHAR(40) NULL,
    [RprodName] NVARCHAR(40) NULL,
    [Net] INT NULL,
    [RNet] BIGINT NULL,
    [supply] NVARCHAR(35) NULL,
    [RSupply] NVARCHAR(35) NULL,
    [SNet] BIGINT NULL,
    [RSNet] BIGINT NULL,
    [NNet] BIGINT NULL,
    [RNNet] BIGINT NULL,
    [ArrDate] VARCHAR(8) NULL,
    [ArrTime] VARCHAR(6) NULL,
    [LeftDate] VARCHAR(8) NULL,
    [LeftTime] VARCHAR(6) NULL,
    [WHNo] VARCHAR(4) NULL,
    [abFlag] NVARCHAR(1) NULL,
    [abReason] VARCHAR(50) NULL,
    [absultion] VARCHAR(10) NULL,
    [SpecUserNo] VARCHAR(50) NULL,
    [version] INT NULL,
    [ABUserNo] NVARCHAR(10) NULL,
    [Instatus] VARCHAR(1) NULL,
    [OutStatus] VARCHAR(1) NULL,
    [TaskProc] VARCHAR(10) NULL,
    [printNum] INT NULL,
    [WeightMan1] NVARCHAR(50) NULL,
    [WeightMan2] NVARCHAR(50) NULL,
    [weightman3] NVARCHAR(50) NULL,
    [weightman4] NVARCHAR(50) NULL,
    [tranflag] NVARCHAR(50) NULL,
    [isCancel] NVARCHAR(50) NULL,
    [FTare] NVARCHAR(50) NULL,
    [TTare] NVARCHAR(50) NULL,
    [FNet] NVARCHAR(50) NULL,
    [TNet] NVARCHAR(50) NULL,
    [underwrite] NVARCHAR(50) NULL,
    [PortNo1] NVARCHAR(3) NULL,
    [portNo2] NVARCHAR(3) NULL,
    [portNo3] NVARCHAR(3) NULL,
    [portNo4] NVARCHAR(3) NULL,
    [InStoreTime] DATETIME NULL,
    [outStoreTime] DATETIME NULL,
    [weigth1] INT NULL,
    [weigth2] INT NULL,
    [weigth3] INT NULL,
    [weigth4] INT NULL,
    [absultion2] VARCHAR(10) NULL,
    [SpecUserNo2] VARCHAR(20) NULL,
    [abReason2] VARCHAR(50) NULL,
    [CalType] INT NULL,
    [OutPrintNum] INT NULL,
    [workFlow] CHAR(1) NULL,
    [BoatNo] VARCHAR(20) NULL,
    [Drivers] VARCHAR(40) NULL,
    [DelReason] VARCHAR(40) NULL,
    [DelFlag] BIT NULL DEFAULT ((0)),
    [BatchNo] VARCHAR(50) NULL
);
GO
  

-- ----------------------------------------
-- Table: [dbo].[cmm_scaleb]
-- ----------------------------------------
CREATE TABLE [dbo].[cmm_scaleb] (
    [compNo] VARCHAR(4) NULL,
    [plantNo] CHAR(4) NULL,
    [DBNo] VARCHAR(10) NOT NULL,
    [TruckNo] VARCHAR(20) NULL,
    [RTruckNo] VARCHAR(20) NULL,
    [potype] VARCHAR(20) NULL,
    [PoNo] VARCHAR(20) NULL,
    [RPoNo] VARCHAR(20) NULL,
    [prodName] NVARCHAR(40) NULL,
    [RprodName] NVARCHAR(40) NULL,
    [Net] INT NULL,
    [RNet] BIGINT NULL,
    [supply] NVARCHAR(35) NULL,
    [RSupply] NVARCHAR(35) NULL,
    [SNet] BIGINT NULL,
    [RSNet] BIGINT NULL,
    [NNet] BIGINT NULL,
    [RNNet] BIGINT NULL,
    [ArrDate] VARCHAR(8) NULL,
    [ArrTime] VARCHAR(6) NULL,
    [LeftDate] VARCHAR(8) NULL,
    [LeftTime] VARCHAR(6) NULL,
    [WHNo] VARCHAR(4) NULL,
    [abFlag] NVARCHAR(1) NULL,
    [abReason] VARCHAR(50) NULL,
    [absultion] VARCHAR(10) NULL,
    [SpecUserNo] VARCHAR(10) NULL,
    [version] INT NULL,
    [ABUserNo] NVARCHAR(10) NULL,
    [Instatus] VARCHAR(1) NULL,
    [OutStatus] VARCHAR(1) NULL,
    [TaskProc] VARCHAR(10) NULL,
    [printNum] INT NULL,
    [WeightMan1] NVARCHAR(50) NULL,
    [WeightMan2] NVARCHAR(50) NULL,
    [weightman3] NVARCHAR(50) NULL,
    [weightman4] NVARCHAR(50) NULL,
    [tranflag] NVARCHAR(50) NULL,
    [isCancel] NVARCHAR(50) NULL,
    [FTare] NVARCHAR(50) NULL,
    [TTare] NVARCHAR(50) NULL,
    [FNet] NVARCHAR(50) NULL,
    [TNet] NVARCHAR(50) NULL,
    [underwrite] NVARCHAR(50) NULL,
    [PortNo1] NVARCHAR(3) NULL,
    [portNo2] NVARCHAR(3) NULL,
    [portNo3] NVARCHAR(3) NULL,
    [portNo4] NVARCHAR(3) NULL,
    [InStoreTime] DATETIME NULL,
    [outStoreTime] CHAR(10) NULL,
    [weigth1] INT NULL,
    [weigth2] INT NULL,
    [weigth3] INT NULL,
    [weigth4] INT NULL,
    [absultion2] VARCHAR(10) NULL,
    [SpecUserNo2] VARCHAR(10) NULL,
    [abReason2] VARCHAR(50) NULL,
    [CalType] INT NULL,
    [OutPrintNum] INT NULL,
    [workFlow] CHAR(1) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[COMPANIES]
-- ----------------------------------------
CREATE TABLE [dbo].[COMPANIES] (
    [ID] DECIMAL(19, 0) NOT NULL,
    [VERSION] DECIMAL(19, 0) NOT NULL,
    [COMPNO] VARCHAR(20) NULL,
    [FULLNAME] VARCHAR(100) NULL,
    [ABBRNAME] VARCHAR(100) NULL,
    [ADDR] VARCHAR(100) NULL,
    [POSTCODE] VARCHAR(6) NULL,
    [INVTITLE] VARCHAR(100) NULL,
    [INVADDR] VARCHAR(100) NULL,
    [TAXNO] VARCHAR(50) NULL,
    [BANK] VARCHAR(100) NULL,
    [ACCOUNT] VARCHAR(50) NULL,
    [TELNO] VARCHAR(50) NULL,
    [FAXNO] VARCHAR(50) NULL,
    [URL] VARCHAR(50) NULL,
    [EMAIL] VARCHAR(50) NULL,
    [REMARKS] VARCHAR(8000) NULL,
    [CUSERNO] VARCHAR(20) NULL,
    [CDATE] DATETIME NULL,
    [LUSERNO] VARCHAR(20) NULL,
    [LDATE] DATETIME NULL
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[cyrange]
-- ----------------------------------------
CREATE TABLE [dbo].[cyrange] (
    [weigthrange] FLOAT NOT NULL,
    [compNo] CHAR(4) NOT NULL,
    [plantNo] CHAR(4) NOT NULL,
    [companyname] VARCHAR(50) NULL,
    [plantName] VARCHAR(50) NULL,
    CONSTRAINT [PK_cyrange] PRIMARY KEY ([compNo], [plantNo])
);
GO
  

-- ----------------------------------------
-- Table: [dbo].[DayPlanList]
-- ----------------------------------------
CREATE TABLE [dbo].[DayPlanList] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [PoNo] VARCHAR(12) NOT NULL,
    [Prq] DATETIME NOT NULL,
    [Pnum] INT NOT NULL,
    [OP] VARCHAR(10) NOT NULL,
    [Intime] DATETIME NOT NULL DEFAULT (getdate()),
    [MAKTX] NVARCHAR(40) NULL,
    [NAME1] NVARCHAR(35) NULL,
    [INqty] INT NULL,
    CONSTRAINT [PK__DayPlanL__F8971430E3DDEA35] PRIMARY KEY ([PoNo], [Prq])
);
GO

-- ----------------------------------------
-- Table: [dbo].[DayPlanListFail]
-- ----------------------------------------
CREATE TABLE [dbo].[DayPlanListFail] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [PoNo] VARCHAR(12) NOT NULL,
    [Prq] DATETIME NOT NULL,
    [Pnum] INT NOT NULL,
    [OP] VARCHAR(10) NOT NULL,
    [Intime] DATETIME NOT NULL DEFAULT (getdate()),
    [MAKTX] NVARCHAR(40) NULL,
    [NAME1] NVARCHAR(35) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[dbgroup]
-- ----------------------------------------
CREATE TABLE [dbo].[dbgroup] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [DBGroupNo] NVARCHAR(2) NULL,
    [dbNo] NVARCHAR(50) NULL,
    [lister] NVARCHAR(50) NULL,
    [listDate] DATETIME NULL,
    [editor] NVARCHAR(50) NULL,
    [editDate] DATETIME NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[dbpo]
-- ----------------------------------------
CREATE TABLE [dbo].[dbpo] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [plantNo] NVARCHAR(4) NULL,
    [compNo] NVARCHAR(4) NULL,
    [poNo] NVARCHAR(50) NULL,
    [DbGroupNo] NVARCHAR(2) NULL,
    [cdate] DATETIME NULL,
    [potype] NVARCHAR(50) NULL,
    [lister] VARCHAR(12) NULL,
    [ltdate] DATETIME NULL,
    [editor] VARCHAR(12) NULL,
    [editdate] DATETIME NULL,
    [used] BIT NULL DEFAULT (0),
    [tosap] BIT NULL DEFAULT ((0))
);
GO
 
  

-- ----------------------------------------
-- Table: [dbo].[DHNO]
-- ----------------------------------------
CREATE TABLE [dbo].[DHNO] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [PoNo] VARCHAR(50) NULL
);
GO
 
 
  

-- ----------------------------------------
-- Table: [dbo].[FacMaterial]
-- ----------------------------------------
CREATE TABLE [dbo].[FacMaterial] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [No] VARCHAR(10) NOT NULL,
    [Pono] VARCHAR(50) NOT NULL,
    [Markx] VARCHAR(255) NOT NULL,
    [Truckno] VARCHAR(100) NOT NULL,
    [Menge] FLOAT NOT NULL,
    [rq] VARCHAR(50) NOT NULL,
    [indate] DATETIME2 NOT NULL DEFAULT (getdate()),
    [bz] VARCHAR(255) NULL,
    [Name1] VARCHAR(255) NULL,
    [Flag] INT NOT NULL DEFAULT ((0)),
    [userin] VARCHAR(255) NULL,
    CONSTRAINT [PK__FacMater__3214D4A89DFB1B1F] PRIMARY KEY ([No])
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[FacMaterialTemp]
-- ----------------------------------------
CREATE TABLE [dbo].[FacMaterialTemp] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [No] VARCHAR(10) NOT NULL,
    [Pono] VARCHAR(50) NOT NULL,
    [Markx] VARCHAR(255) NOT NULL,
    [Truckno] VARCHAR(100) NOT NULL,
    [Menge] FLOAT NOT NULL,
    [rq] VARCHAR(50) NOT NULL,
    [indate] DATETIME NOT NULL DEFAULT (getdate()),
    [bz] VARCHAR(255) NULL,
    [Name1] VARCHAR(255) NULL,
    [Flag] INT NOT NULL DEFAULT ((0)),
    [pob] BIT NOT NULL DEFAULT ((0)),
    [rqb] BIT NOT NULL DEFAULT ((0)),
    [numb] BIT NOT NULL DEFAULT ((0)),
    [userin] VARCHAR(255) NULL,
    CONSTRAINT [PK__FacMater__3214D4A8BA501E1F] PRIMARY KEY ([No])
);
GO
   

-- ----------------------------------------
-- Table: [dbo].[MailParas]
-- ----------------------------------------
CREATE TABLE [dbo].[MailParas] (
    [MailID] VARCHAR(20) NOT NULL,
    [MailType] NVARCHAR(20) NOT NULL,
    [MailTitle] NVARCHAR(100) NOT NULL,
    [MailBody] NVARCHAR(800) NOT NULL DEFAULT (''),
    [SendTo] VARCHAR(1000) NOT NULL,
    [SQLCmd] NVARCHAR(1000) NULL,
    [FileName] NVARCHAR(50) NULL,
    [FieldTitle] NVARCHAR(800) NULL,
    [IsExport] BIT NOT NULL DEFAULT ((0)),
    [IsUse] BIT NOT NULL DEFAULT ((1)),
    [Islog] BIT NULL DEFAULT ((0)),
    [colspan] NVARCHAR(100) NULL DEFAULT (''),
    [rowspan] NVARCHAR(100) NULL DEFAULT (''),
    [IsCount] BIT NULL DEFAULT ((0)),
    [Remark] NVARCHAR(200) NULL,
    [Upstatus] BIT NULL DEFAULT ((0)),
    [curday] SMALLINT NULL,
    [fontsize] VARCHAR(10) NULL,
    CONSTRAINT [PK_MailParas] PRIMARY KEY ([MailID])
);
GO
 
 
 

-- ----------------------------------------
-- Table: [dbo].[MM_A1WGT_LOG]
-- ----------------------------------------
CREATE TABLE [dbo].[MM_A1WGT_LOG] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [PLANTNO] VARCHAR(50) NULL,
    [COMPNO] VARCHAR(50) NULL,
    [AUFNR] VARCHAR(50) NULL,
    [TRUCKNO] VARCHAR(50) NULL,
    [A1] INT NULL,
    [OP_NAME] VARCHAR(50) NULL,
    [OP_TIME] DATETIME NULL,
    [B1] INT NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[MM_POWO_SCALE]
-- ----------------------------------------
CREATE TABLE [dbo].[MM_POWO_SCALE] (
    [BUKRS] CHAR(4) NOT NULL,
    [WERKS] CHAR(4) NOT NULL,
    [AUFNR] VARCHAR(20) NOT NULL,
    [ORTYP] CHAR(1) NULL,
    [MAKTX] NVARCHAR(40) NULL,
    [NAME1] NVARCHAR(35) NULL,
    [KDATE] CHAR(8) NULL,
    [EDATE] CHAR(8) NULL,
    [ERNAM] NVARCHAR(12) NULL,
    [TRUCKNO] VARCHAR(20) NULL,
    [MENGE] DECIMAL(13, 3) NULL,
    [UEBTO] DECIMAL(3, 1) NULL,
    [InQty] NUMERIC(14, 3) NULL DEFAULT ((0)),
    [DRDATE] DATETIME NULL DEFAULT (getdate()),
    [PutSupWgt] BIT NULL,
    [closed] BIT NULL DEFAULT ((0)),
    CONSTRAINT [PK_MM_POWO_SCALE] PRIMARY KEY ([BUKRS], [WERKS], [AUFNR])
);
GO

-- ----------------------------------------
-- Table: [dbo].[MM_RW_Card]
-- ----------------------------------------
CREATE TABLE [dbo].[MM_RW_Card] (
    [ID] BIGINT IDENTITY(1,1) NOT NULL,
    [CardID] VARCHAR(14) NULL,
    [TruckNo] NVARCHAR(20) NULL,
    [InDate] DATETIME NULL,
    [pono] VARCHAR(20) NULL,
    [dbno] VARCHAR(14) NULL,
    [flags] INT NULL DEFAULT ((0)),
    [rscode] INT NULL,
    [WgtMax] VARCHAR(10) NULL,
    [rmks] VARCHAR(60) NULL,
    [drivers] VARCHAR(30) NULL,
    [MTel] VARCHAR(20) NULL,
    [rks] VARCHAR(30) NULL,
    [SupWgt] VARCHAR(10) NULL DEFAULT (''),
    CONSTRAINT [PK_MM_RW_Card] PRIMARY KEY ([ID])
);
GO

-- ----------------------------------------
-- Table: [dbo].[MM_SCALE]
-- ----------------------------------------
CREATE TABLE [dbo].[MM_SCALE] (
    [BUKRS] CHAR(4) NOT NULL,
    [WERKS] CHAR(4) NOT NULL,
    [RECNO] VARCHAR(10) NOT NULL,
    [VERNO] CHAR(1) NOT NULL,
    [CARNO] VARCHAR(50) NULL,
    [CARNO_MDY] VARCHAR(50) NULL,
    [ORDNO] VARCHAR(20) NULL,
    [ORDNO_MDY] VARCHAR(20) NULL,
    [MTRTX] NVARCHAR(40) NULL,
    [MTRTX_MDY] NVARCHAR(40) NULL,
    [LIFNA] NVARCHAR(35) NULL,
    [LIFNA_MDY] NVARCHAR(35) NULL,
    [LGORT] CHAR(4) NULL,
    [LGORT_MDY] CHAR(4) NULL,
    [NETWT] VARCHAR(10) NULL,
    [NETWT_MDY] CHAR(6) NULL,
    [VEDWT] CHAR(6) NULL,
    [VEDWT_MDY] CHAR(6) NULL,
    [NUTWT] CHAR(6) NULL,
    [NUTWT_MDY] CHAR(6) NULL,
    [MEINS] CHAR(3) NULL,
    [ENTDA] CHAR(8) NULL,
    [ENTTM] CHAR(6) NULL,
    [LEVDA] CHAR(8) NULL,
    [LEVTM] CHAR(6) NULL,
    [ANOFG_IM] CHAR(1) NULL,
    [ANORS_IM] NVARCHAR(50) NULL,
    [ANODL_IM] NVARCHAR(50) NULL,
    [ANOAC_IM] NVARCHAR(50) NULL,
    [ANOFG_EX] CHAR(1) NULL,
    [ANORS_EX] NVARCHAR(50) NULL,
    [ANODL_EX] NVARCHAR(50) NULL,
    [ANOAC_EX] NVARCHAR(50) NULL,
    [RETCODE] CHAR(3) NULL,
    [RETMESG] VARCHAR(132) NULL,
    [ZWORKFLOW] CHAR(1) NULL,
    [A1_WT] CHAR(6) NULL,
    [A2_WT] CHAR(6) NULL,
    [B2_WT] CHAR(6) NULL,
    [B1_WT] CHAR(6) NULL,
    [BATCHNO] VARCHAR(50) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[MM_SCALE_History]
-- ----------------------------------------
CREATE TABLE [dbo].[MM_SCALE_History] (
    [BUKRS] CHAR(4) NOT NULL,
    [WERKS] CHAR(4) NOT NULL,
    [RECNO] VARCHAR(10) NOT NULL,
    [VERNO] CHAR(1) NOT NULL,
    [CARNO] VARCHAR(50) NULL,
    [CARNO_MDY] VARCHAR(50) NULL,
    [ORDNO] VARCHAR(20) NULL,
    [ORDNO_MDY] VARCHAR(20) NULL,
    [MTRTX] NVARCHAR(40) NULL,
    [MTRTX_MDY] NVARCHAR(40) NULL,
    [LIFNA] NVARCHAR(35) NULL,
    [LIFNA_MDY] NVARCHAR(35) NULL,
    [LGORT] CHAR(4) NULL,
    [LGORT_MDY] CHAR(4) NULL,
    [NETWT] VARCHAR(10) NULL,
    [NETWT_MDY] CHAR(6) NULL,
    [VEDWT] CHAR(6) NULL,
    [VEDWT_MDY] CHAR(6) NULL,
    [NUTWT] CHAR(6) NULL,
    [NUTWT_MDY] CHAR(6) NULL,
    [MEINS] CHAR(3) NULL DEFAULT ('KG'),
    [ENTDA] CHAR(8) NULL,
    [ENTTM] CHAR(6) NULL,
    [LEVDA] CHAR(8) NULL,
    [LEVTM] CHAR(6) NULL,
    [ANOFG_IM] CHAR(1) NULL,
    [ANORS_IM] NVARCHAR(50) NULL,
    [ANODL_IM] NVARCHAR(50) NULL,
    [ANOAC_IM] NVARCHAR(50) NULL,
    [ANOFG_EX] CHAR(1) NULL,
    [ANORS_EX] NVARCHAR(50) NULL,
    [ANODL_EX] NVARCHAR(50) NULL,
    [ANOAC_EX] NVARCHAR(50) NULL,
    [RETCODE] CHAR(3) NULL,
    [RETMESG] VARCHAR(132) NULL,
    [ZWORKFLOW] CHAR(1) NULL,
    [A1_WT] CHAR(6) NULL,
    [A2_WT] CHAR(6) NULL,
    [B2_WT] CHAR(6) NULL,
    [B1_WT] CHAR(6) NULL,
    [BATCHNO] VARCHAR(50) NULL,
    CONSTRAINT [PK__MM_SCALE__01E27DDC5B8A2CA8] PRIMARY KEY ([BUKRS], [WERKS], [RECNO], [VERNO])
);
GO
 
-- ----------------------------------------
-- Table: [dbo].[MMDB]
-- ----------------------------------------
CREATE TABLE [dbo].[MMDB] (
    [Pono] VARCHAR(20) NULL,
    [SEQ_NO] VARCHAR(3) NULL,
    [SLDBNO] VARCHAR(10) NULL,
    [MCDBNO] VARCHAR(10) NULL,
    [TruckNo] VARCHAR(20) NOT NULL,
    [LeftDate] VARCHAR(8) NOT NULL,
    [LeftTime] VARCHAR(6) NOT NULL,
    [YnCheck] BIT NOT NULL DEFAULT ((0)),
    [DBNO] VARCHAR(10) NULL,
    [createdate] DATETIME NOT NULL DEFAULT (getdate()),
    [PLANTNO] VARCHAR(20) NULL,
    [PLANTID] NUMERIC(19, 0) NULL,
    [mtarrdate] VARCHAR(8) NULL,
    [mtarrtime] VARCHAR(6) NULL,
    [mtleftdate] VARCHAR(8) NULL,
    [mtlefttime] VARCHAR(6) NULL,
    [mtnet] INT NULL,
    [mtttare] VARCHAR(50) NULL,
    [mtweight] VARCHAR(50) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMInstall]
-- ----------------------------------------
CREATE TABLE [dbo].[MMInstall] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [LocalIP] VARCHAR(20) NOT NULL,
    [LocalVersion] NVARCHAR(20) NULL,
    [InstallTime] DATETIME NULL,
    [hostname] VARCHAR(200) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMLog]
-- ----------------------------------------
CREATE TABLE [dbo].[MMLog] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [LocalIP] VARCHAR(20) NOT NULL,
    [LocalVersion] NVARCHAR(20) NULL,
    [MMModule] NVARCHAR(255) NULL,
    [OPTor] NVARCHAR(20) NULL,
    [OPTime] DATETIME NULL
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[MMPARAS]
-- ----------------------------------------
CREATE TABLE [dbo].[MMPARAS] (
    [PARACODE] VARCHAR(50) NOT NULL,
    [PARASTR] VARCHAR(255) NULL,
    [PARAINT] NUMERIC(18, 6) NULL,
    [PARABOOL] BIT NULL,
    [REMARKS] VARCHAR(255) NULL,
    CONSTRAINT [PK__MMPARAS__17236851] PRIMARY KEY ([PARACODE])
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMPasswordWarn]
-- ----------------------------------------
CREATE TABLE [dbo].[MMPasswordWarn] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [Content] VARCHAR(2000) NOT NULL,
    [issend] BIT NOT NULL DEFAULT ((0))
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMSign]
-- ----------------------------------------
CREATE TABLE [dbo].[MMSign] (
    [dbno] VARCHAR(16) NOT NULL,
    [Signmap] IMAGE NULL,
    [SignDate] DATETIME NULL DEFAULT (CONVERT([varchar](20),getdate(),(120))),
    CONSTRAINT [PK_MMSign] PRIMARY KEY ([dbno])
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMVer]
-- ----------------------------------------
CREATE TABLE [dbo].[MMVer] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [LocalVersion] NVARCHAR(20) NULL,
    [OPTime] DATETIME NULL,
    [Send] BIT NOT NULL DEFAULT ((0))
);
GO

-- ----------------------------------------
-- Table: [dbo].[MMWeighrec]
-- ----------------------------------------
CREATE TABLE [dbo].[MMWeighrec] (
    [ID] BIGINT IDENTITY(1,1) NOT NULL,
    [Dbno] VARCHAR(20) NULL,
    [WgtNO] VARCHAR(10) NULL,
    [WgtValue] INT NULL,
    [CDate] DATETIME NULL DEFAULT (getdate()),
    [CUser] VARCHAR(20) NULL,
    CONSTRAINT [PK_MMWeighrec] PRIMARY KEY ([ID])
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[params]
-- ----------------------------------------
CREATE TABLE [dbo].[params] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [DbGroupNo] NVARCHAR(1) NULL,
    [Reason] NVARCHAR(50) NULL,
    [UserNo] NVARCHAR(20) NULL,
    [Cdate] DATETIME NULL,
    CONSTRAINT [PK_params] PRIMARY KEY ([ID])
);
GO
 
-- ----------------------------------------
-- Table: [dbo].[PLANTS]
-- ----------------------------------------
CREATE TABLE [dbo].[PLANTS] (
    [ID] NUMERIC(19, 0) NOT NULL,
    [VERSION] NUMERIC(19, 0) NOT NULL,
    [PLANTNO] VARCHAR(20) NOT NULL,
    [PNAME] NVARCHAR(100) NULL,
    [ADDR] NVARCHAR(100) NULL,
    [POSTCODE] VARCHAR(6) NULL,
    [TELNO] VARCHAR(50) NULL,
    [FAXNO] VARCHAR(50) NULL,
    [PRINCIPAL] NVARCHAR(50) NULL,
    [ISCENTER] VARCHAR(1) NULL,
    [CUSERNO] VARCHAR(20) NULL,
    [CDATE] DATETIME NULL,
    [LUSERNO] VARCHAR(20) NULL,
    [LDATE] DATETIME NULL,
    [CUSTID] NUMERIC(18, 0) NULL,
    [IsSimpleShipment] BIT NULL,
    [IsNoneScale] BIT NULL,
    [IsFBSYS] BIT NULL,
    [CreditCode] VARCHAR(30) NULL,
    CONSTRAINT [PK_PLANTS] PRIMARY KEY ([ID])
);
GO
  
 

-- ----------------------------------------
-- Table: [dbo].[SYSPARAS]
-- ----------------------------------------
CREATE TABLE [dbo].[SYSPARAS] (
    [PARACODE] VARCHAR(50) NOT NULL,
    [PARASTR] VARCHAR(128) NULL,
    [PARAINT] NUMERIC(18, 6) NULL,
    [PARABOOL] BIT NULL,
    [REMARKS] VARCHAR(255) NULL,
    CONSTRAINT [PK_SYSPARAS] PRIMARY KEY ([PARACODE])
);
GO

-- ----------------------------------------
-- Table: [dbo].[tbuser_menu]
-- ----------------------------------------
CREATE TABLE [dbo].[tbuser_menu] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [MenuNo] VARCHAR(10) NULL,
    [MenuName] VARCHAR(50) NULL,
    [UserNo] VARCHAR(30) NULL,
    [Enable] BIT NULL,
    CONSTRAINT [PK__tbuser_m__3213E83FC36B2051] PRIMARY KEY ([id])
);
GO

-- ----------------------------------------
-- Table: [dbo].[TEMPDBMM]
-- ----------------------------------------
CREATE TABLE [dbo].[TEMPDBMM] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [DBNO] VARCHAR(10) NULL,
    [MCDBNO] VARCHAR(10) NULL,
    [TruckNo] VARCHAR(20) NOT NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[TEMPMMC]
-- ----------------------------------------
CREATE TABLE [dbo].[TEMPMMC] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [DBNO] VARCHAR(10) NULL,
    [TruckNo] VARCHAR(20) NOT NULL
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[trace_mstr]
-- ----------------------------------------
CREATE TABLE [dbo].[trace_mstr] (
    [id] VARCHAR(12) NOT NULL,
    [inputpoint] VARCHAR(2) NOT NULL,
    [dbno] CHAR(10) NOT NULL,
    [version] CHAR(1) NOT NULL,
    [pono] VARCHAR(50) NULL,
    [hddate] CHAR(8) NULL,
    [hdtime] CHAR(6) NULL,
    [eventname] VARCHAR(50) NULL,
    [truckno] NVARCHAR(50) NULL,
    [supply] NVARCHAR(50) NULL,
    [prodname] NVARCHAR(50) NULL,
    [modprodname] NVARCHAR(50) NULL,
    [modsupply] NVARCHAR(50) NULL,
    [modpono] VARCHAR(20) NULL,
    [modtruckno] NVARCHAR(50) NULL,
    [A1_WT] VARCHAR(8) NULL,
    [A2_WT] VARCHAR(8) NULL,
    [B2_WT] VARCHAR(8) NULL,
    [B1_WT] VARCHAR(8) NULL,
    [userno] VARCHAR(20) NULL,
    [instatus] CHAR(1) NULL,
    [inreason] NVARCHAR(40) NULL,
    [insolution] NVARCHAR(40) NULL,
    [inexcepuserno] NVARCHAR(20) NULL,
    [outstatus] VARCHAR(20) NULL,
    [outreason] NVARCHAR(40) NULL,
    [outsolution] NVARCHAR(40) NULL,
    [outexcepuserno] VARCHAR(20) NULL,
    [workflow] CHAR(1) NULL
);
GO

CREATE NONCLUSTERED INDEX [IX_trace_mstr]
    ON [dbo].[trace_mstr] ([id], [dbno], [inputpoint]);
GO

CREATE NONCLUSTERED INDEX [IX_trace_mstr_1]
    ON [dbo].[trace_mstr] ([id], [dbno]);
GO
 

-- ----------------------------------------
-- Table: [dbo].[truck]
-- ----------------------------------------
CREATE TABLE [dbo].[truck] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [truckno] VARCHAR(50) NOT NULL,
    [trancomp] VARCHAR(50) NOT NULL,
    [op] VARCHAR(50) NULL,
    [intime] DATE NULL DEFAULT (getdate()),
    [TruckType] VARCHAR(10) NULL,
    [DriverNO] VARCHAR(40) NULL,
    [PL] VARCHAR(255) NULL,
    [bz] VARCHAR(255) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[TruckList]
-- ----------------------------------------
CREATE TABLE [dbo].[TruckList] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [TruckNo] VARCHAR(10) NOT NULL,
    [TruckType] VARCHAR(10) NOT NULL,
    [IsBlack] BIT NOT NULL DEFAULT ((0)),
    [Intime] DATETIME NOT NULL DEFAULT (getdate()),
    [trancomp] VARCHAR(40) NULL,
    [DriverNO] VARCHAR(40) NULL,
    [PL] VARCHAR(255) NULL,
    [bz] VARCHAR(255) NULL,
    [op] VARCHAR(50) NULL,
    CONSTRAINT [PK__TruckLis__6635BA986C065D68] PRIMARY KEY ([TruckNo])
);
GO

-- ----------------------------------------
-- Table: [dbo].[TruckListFail]
-- ----------------------------------------
CREATE TABLE [dbo].[TruckListFail] (
    [Id] INT IDENTITY(1,1) NOT NULL,
    [TruckNo] VARCHAR(10) NOT NULL,
    [TruckType] VARCHAR(10) NOT NULL,
    [IsBlack] BIT NOT NULL DEFAULT ((0)),
    [Intime] DATETIME NOT NULL DEFAULT (getdate()),
    [trancomp] VARCHAR(40) NULL,
    [DriverNO] VARCHAR(40) NULL,
    [PL] VARCHAR(255) NULL,
    [bz] VARCHAR(255) NULL,
    [op] VARCHAR(50) NULL,
    CONSTRAINT [PK__TruckLis__6635BA9817777E27] PRIMARY KEY ([TruckNo])
);
GO

-- ----------------------------------------
-- Table: [dbo].[TruckLTime]
-- ----------------------------------------
CREATE TABLE [dbo].[TruckLTime] (
    [Truckno] NVARCHAR(40) NOT NULL,
    [TranCode] NVARCHAR(10) NOT NULL DEFAULT (''),
    [Ltime] DATETIME NOT NULL DEFAULT (getdate()),
    [dono] VARCHAR(20) NOT NULL DEFAULT (''),
    CONSTRAINT [PK_TruckLTime] PRIMARY KEY ([Truckno], [TranCode])
);
GO
 

-- ----------------------------------------
-- Table: [dbo].[user_mstr1]
-- ----------------------------------------
CREATE TABLE [dbo].[user_mstr1] (
    [userNo] VARCHAR(12) NOT NULL,
    [name] NVARCHAR(50) NULL,
    [password] NVARCHAR(50) NULL,
    [userkind] NVARCHAR(50) NULL,
    [createDate] DATETIME NULL,
    [GroupNo] VARCHAR(10) NULL,
    [EMPLOYEEID] VARCHAR(30) NULL DEFAULT (''),
    [lgdate] DATETIME NULL,
    [emdate] DATETIME NULL,
    [IsLock] BIT NULL DEFAULT ((0)),
    [chgpwdtime] DATETIME NULL DEFAULT (CONVERT([varchar](20),getdate(),(120))),
    [bz] VARCHAR(255) NULL,
    CONSTRAINT [PK_user_mstr] PRIMARY KEY ([userNo])
);
GO

CREATE UNIQUE NONCLUSTERED INDEX [IX_user_mstr]
    ON [dbo].[user_mstr1] ([userNo]);
GO

-- ----------------------------------------
-- Table: [dbo].[user_mstr1DEL]
-- ----------------------------------------
CREATE TABLE [dbo].[user_mstr1DEL] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [userNo] VARCHAR(12) NOT NULL,
    [name] NVARCHAR(50) NULL,
    [password] NVARCHAR(50) NULL,
    [userkind] NVARCHAR(50) NULL,
    [createDate] DATETIME NULL,
    [GroupNo] VARCHAR(30) NULL,
    [EMPLOYEEID] VARCHAR(30) NULL DEFAULT (''),
    [lgdate] DATETIME NULL,
    [emdate] DATETIME NULL,
    [islock] BIT NOT NULL DEFAULT ((0)),
    [chgpwdtime] DATETIME NULL DEFAULT (CONVERT([varchar](20),getdate(),(120))),
    [opdate] DATETIME NULL,
    [bz] VARCHAR(255) NULL
);
GO

-- ----------------------------------------
-- Table: [dbo].[UserADDrecord]
-- ----------------------------------------
CREATE TABLE [dbo].[UserADDrecord] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [userno] NVARCHAR(50) NULL,
    [username] NVARCHAR(50) NULL,
    [opname] NVARCHAR(50) NULL,
    [opdate] DATETIME NOT NULL DEFAULT (getdate()),
    [bz] NVARCHAR(255) NULL,
    [stype] VARCHAR(10) NOT NULL,
    [password] NVARCHAR(50) NULL
);
GO

CREATE UNIQUE NONCLUSTERED INDEX [noandtype]
    ON [dbo].[UserADDrecord] ([userno], [stype]);
GO

-- ----------------------------------------
-- Table: [dbo].[UserChgPwd]
-- ----------------------------------------
CREATE TABLE [dbo].[UserChgPwd] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [SName] VARCHAR(10) NOT NULL,
    [UserId] VARCHAR(20) NOT NULL,
    [Pwd] NVARCHAR(120) NOT NULL,
    [CDate] DATETIME NULL DEFAULT (CONVERT([varchar](20),getdate(),(120)))
);
GO

-- ----------------------------------------
-- Table: [dbo].[userdelrecord]
-- ----------------------------------------
CREATE TABLE [dbo].[userdelrecord] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [userno] NVARCHAR(50) NULL,
    [username] NVARCHAR(50) NULL,
    [opname] NVARCHAR(50) NULL,
    [opdate] DATETIME NOT NULL DEFAULT (getdate()),
    [bz] NVARCHAR(255) NULL,
    [stype] VARCHAR(10) NOT NULL,
    [password] NVARCHAR(50) NULL
);
GO

CREATE UNIQUE NONCLUSTERED INDEX [noandtype]
    ON [dbo].[userdelrecord] ([userno], [stype]);
GO

-- ----------------------------------------
-- Table: [dbo].[Warnlog]
-- ----------------------------------------
CREATE TABLE [dbo].[Warnlog] (
    [ID] INT IDENTITY(1,1) NOT NULL,
    [PLANTNO] VARCHAR(50) NULL,
    [COMPNO] VARCHAR(50) NULL,
    [DBNO] VARCHAR(50) NULL,
    [AUFNR] VARCHAR(50) NULL,
    [TRUCKNO] VARCHAR(50) NULL,
    [QTY] INT NULL,
    [LOAD_QTY] INT NULL,
    [CURREENT_QTY] INT NULL,
    [LOG] VARCHAR(500) NULL,
    [OP_NAME] VARCHAR(50) NULL,
    [OP_TIME] DATETIME NULL
);
GO
 
 
